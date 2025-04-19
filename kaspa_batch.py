'''
* Author : Rymentz
* Version : v1.0.0
'''

import subprocess
import time
import logging
import getpass
import os
import re
from datetime import datetime

# Configuration
REDISTRIBUTION_FILE = "redistribution.txt"
DEBUG_MODE = False  # Debug mode

# Log configuration
LOG_DIRECTORY = "logs"
if not os.path.exists(LOG_DIRECTORY):
    os.makedirs(LOG_DIRECTORY)

LOG_FILENAME = os.path.join(LOG_DIRECTORY, f"kaspa_transfers_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

# Configure logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILENAME),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger()
if DEBUG_MODE:
    logger.setLevel(logging.DEBUG)

# Network-specific configuration
NETWORK_CONFIGS = {
    "mainnet": {
        "network_cmd": "network mainnet",
        "connect_cmd": "connect wss://anna.kaspa.stream/kaspa/mainnet/wrpc/borsh",
        "address_prefix": "kaspa:",
        "currency_symbol": "KAS"
    },
    "testnet": {
        "network_cmd": "network testnet-10",
        "connect_cmd": "connect wss://tau-10.kaspa.blue/kaspa/testnet-10/wrpc/borsh",
        "address_prefix": "kaspatest:",
        "currency_symbol": "TKAS"
    }
}

def read_redistribution_file(file_path, address_prefix):
    """Reads the redistribution file with enhanced validation"""
    transfers = []
    valid_lines = 0
    invalid_lines = 0
    
    if not os.path.exists(file_path):
        logger.error(f"❌ The file {file_path} does not exist!")
        return []
            
    try:
        with open(file_path, 'r') as file:
            content = file.read()
            
            # Check global format
            if "Address,Amount" not in content:
                logger.error(f"❌ Incorrect file format: 'Address,Amount' header missing")
                return []
                
            if "End of redistribution report" not in content:
                logger.warning(f"⚠️ Suspicious file format: 'End of redistribution report' missing")
            
            # Line by line processing
            reading_data = False
            line_number = 0
            
            for line in content.splitlines():
                line_number += 1
                line = line.strip()
                
                if not line:  # Ignore empty lines
                    continue
                    
                if "Address,Amount" in line:
                    reading_data = True
                    continue
                
                if "End of redistribution report" in line:
                    break
                
                if reading_data and ',' in line:
                    parts = line.split(',')
                    if len(parts) >= 2:
                        address = parts[0].strip()
                        amount_str = parts[1].strip()
                        
                        # Address validation
                        valid_address = False
                        if address.startswith(address_prefix):
                            valid_address = True
                        elif not address.startswith("kaspa:") and not address.startswith("kaspatest:"):
                            address = address_prefix + address
                            valid_address = True
                            logger.info(f"Prefix added to address: {address}")
                        elif address.startswith("kaspa:") and address_prefix == "kaspatest:":
                            logger.warning(f"⚠️ Line {line_number}: Mainnet address '{address}' found while network is testnet")
                        elif address.startswith("kaspatest:") and address_prefix == "kaspa:":
                            logger.warning(f"⚠️ Line {line_number}: Testnet address '{address}' found while network is mainnet")
                        
                        # Amount validation
                        try:
                            amount = float(amount_str)
                            if amount <= 0:
                                logger.warning(f"⚠️ Line {line_number}: Invalid amount (must be positive): {amount_str}")
                                invalid_lines += 1
                                continue
                        except ValueError:
                            logger.warning(f"⚠️ Line {line_number}: Non-numeric amount: {amount_str}")
                            invalid_lines += 1
                            continue
                        
                        if valid_address:
                            transfers.append((address, amount_str))
                            valid_lines += 1
                        else:
                            logger.warning(f"⚠️ Line {line_number}: Address ignored as incompatible with the network: {address}")
                            invalid_lines += 1
                    else:
                        logger.warning(f"⚠️ Line {line_number}: Incorrect format (should be 'address,amount'): {line}")
                        invalid_lines += 1
    
    except Exception as e:
        logger.error(f"❌ Error reading file: {e}")
        return []
        
    logger.info(f"Redistribution file: {valid_lines} valid lines, {invalid_lines} invalid lines")
    return transfers

def calculate_total_amount(transfers):
    """Calculates the total amount to transfer"""
    total = 0.0
    fees_estimate = 0.00002036  # Transaction fee estimate per transaction
    
    for _, amount in transfers:
        try:
            amount_float = float(amount)
            total += amount_float
        except ValueError:
            logger.warning(f"Unable to convert amount '{amount}' to number")
    
    total_with_fees = total + (len(transfers) * fees_estimate)
    return total, total_with_fees

def tmux_send_command_with_pattern(session_name, command, expected_pattern=None, max_wait=30, password=False):
    """Sends a command and waits for a specific pattern in the output"""
    # Define default patterns based on the command
    if expected_pattern is None:
        if "network" in command:
            expected_pattern = "Setting network id to:"
        elif "connect" in command:
            expected_pattern = "Connected to Kaspa node"
        elif command == "open":
            expected_pattern = "Enter wallet password:"
        elif "send" in command:
            expected_pattern = "Enter wallet password:"
        elif command == "exit":
            expected_pattern = "bye!"
        else:
            expected_pattern = "$"  # Default, wait for the prompt
    
    # Don't display passwords in logs
    display_cmd = command if not password else "[PASSWORD]"
    logger.info(f"Executing command: {display_cmd}")
    
    # Send the command
    escaped_command = command.replace('"', '\\"')
    cmd = f'tmux send-keys -t {session_name} "{escaped_command}" Enter'
    subprocess.run(cmd, shell=True, check=True)
    
    # Wait for the expected pattern
    start_time = time.time()
    found = False
    
    while time.time() - start_time < max_wait and not found:
        # Capture current output
        output_cmd = f'tmux capture-pane -p -t {session_name}'
        output = subprocess.run(output_cmd, shell=True, check=True, stdout=subprocess.PIPE).stdout.decode('utf-8')
        
        # Check if pattern is present
        if expected_pattern in output:
            found = True
            # If we found a pattern for a password, wait a small additional delay
            if expected_pattern == "Enter wallet password:" or expected_pattern == "Enter payment password:":
                time.sleep(0.5)
        else:
            # Check if we have a new pattern indicating the next state
            if "Enter payment password:" in output and expected_pattern == "Enter wallet password:":
                found = True
            elif "Send - Amount:" in output:
                found = True
        
        if not found:
            time.sleep(0.5)
    
    # If we didn't find the pattern within the timeout
    if not found:
        logger.warning(f"Pattern '{expected_pattern}' not found within {max_wait}s timeout")
    
    # Capture final state for debugging
    if DEBUG_MODE:
        output_cmd = f'tmux capture-pane -p -t {session_name}'
        output = subprocess.run(output_cmd, shell=True, check=True, stdout=subprocess.PIPE).stdout.decode('utf-8')
        logger.debug(f"State after command '{display_cmd}':\n{output}")
    
    return output if found else None

def get_wallet_balance(session_name, currency_symbol):
    """Retrieves the current wallet balance with a robust method"""
    output_cmd = f'tmux capture-pane -p -t {session_name}'
    output = subprocess.run(output_cmd, shell=True, check=True, stdout=subprocess.PIPE).stdout.decode('utf-8')
    
    # Use regex to extract the balance
    balance_pattern = r'•\s*([\d,]+\.\d+)\s*' + re.escape(currency_symbol)
    match = re.search(balance_pattern, output)
    
    if match:
        try:
            # Extract and convert the balance
            balance_str = match.group(1).replace(',', '')
            return float(balance_str)
        except Exception as e:
            logger.debug(f"Regex match found but conversion error: {e}")
    
    # Fallback method if regex fails
    for line in output.split('\n'):
        if currency_symbol in line and "•" in line:
            try:
                # Extract the part after "•" and before the currency symbol
                parts = line.split("•")
                if len(parts) >= 2:
                    balance_text = parts[1].split(currency_symbol)[0].strip()
                    # Remove anything that's not a digit, comma, or period
                    clean_balance = re.sub(r'[^\d,.]', '', balance_text)
                    return float(clean_balance.replace(',', ''))
            except Exception as e:
                logger.debug(f"Fallback attempt failed on line '{line}': {e}")
    
    logger.warning("Unable to extract wallet balance")
    return None

def extract_transaction_id(output):
    """Extracts the transaction ID from the CLI output"""
    try:
        tx_lines = [line for line in output.split('\n') if "tx ids:" in line]
        if tx_lines:
            tx_line = tx_lines[-1]  # Take the last line with tx ids
            if ":" in tx_line:
                tx_id = tx_line.split(":")[-1].strip()
                return tx_id
    except Exception as e:
        logger.debug(f"Error extracting transaction ID: {e}")
    return None

def automate_kaspa_transfers():
    """Automates Kaspa transfers via CLI interface"""
    # Ask user to choose network
    while True:
        network_choice = input("Choose network (mainnet/testnet): ").strip().lower()
        if network_choice in ["mainnet", "testnet"]:
            break
        else:
            print("Please enter 'mainnet' or 'testnet'.")
    
    # Load network configuration
    network_config = NETWORK_CONFIGS[network_choice]
    logger.info(f"Selected network: {network_choice}")
    
    # Check if redistribution file exists
    if not os.path.exists(REDISTRIBUTION_FILE):
        logger.error(f"The file {REDISTRIBUTION_FILE} does not exist!")
        return
    
    # Read redistribution file
    transfers = read_redistribution_file(REDISTRIBUTION_FILE, network_config["address_prefix"])
    if not transfers:
        logger.warning(f"No transfers to make for network {network_choice}. Check the redistribution file.")
        return
    
    # Calculate total amount to transfer
    total_amount, total_with_fees = calculate_total_amount(transfers)
    logger.info(f"Found {len(transfers)} transfers to make for a total of {total_amount} {network_config['currency_symbol']}")
    logger.info(f"Estimated total with fees: {total_with_fees} {network_config['currency_symbol']}")
    
    # Request passwords securely
    wallet_password = getpass.getpass("Enter wallet password: ")
    payment_password = getpass.getpass("Enter payment password (leave empty if same): ")
    
    # If payment password is empty, use wallet password
    if not payment_password:
        payment_password = wallet_password
    
    try:
        # Check if tmux is installed
        try:
            subprocess.run(["tmux", "-V"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except:
            logger.error("tmux is not installed. Please install it with: sudo apt-get install tmux")
            return
        
        # tmux session name
        session_name = f"kaspa_auto_{int(time.time())}"
        
        # Create a new detached tmux session
        logger.info("Creating a tmux session for Kaspa CLI...")
        subprocess.run(f'tmux new-session -d -s {session_name}', shell=True, check=True)
        
        # Initialize Kaspa CLI
        tmux_send_command_with_pattern(session_name, f"cd ~/rusty-kaspa/cli && cargo run --release", "type 'help' for list of commands", 20)
        tmux_send_command_with_pattern(session_name, network_config["network_cmd"], "Setting network id to:")
        tmux_send_command_with_pattern(session_name, network_config["connect_cmd"], "Connected to Kaspa node")
        tmux_send_command_with_pattern(session_name, "open", "Enter wallet password:")
        wallet_output = tmux_send_command_with_pattern(session_name, wallet_password, "Your wallet hint is:", password=True)
        
        # Get wallet balance
        balance = get_wallet_balance(session_name, network_config["currency_symbol"])
        
        if balance is None:
            logger.error("Unable to retrieve wallet balance.")
            logger.info("Closing tmux session...")
            subprocess.run(f'tmux kill-session -t {session_name}', shell=True, check=True)
            return
        
        # Compare balance and total amount
        logger.info(f"Current balance: {balance} {network_config['currency_symbol']}")
        
        if balance < total_with_fees:
            shortfall = total_with_fees - balance
            logger.warning(f"⚠️ INSUFFICIENT BALANCE! Missing {shortfall:.8f} {network_config['currency_symbol']} to make all transfers.")
            
            confirm = input("Balance is insufficient. Do you want to continue with possible transfers anyway? (y/n): ").strip().lower()
            if confirm != 'y':
                logger.info("Operation cancelled by user.")
                logger.info("Closing Kaspa CLI...")
                tmux_send_command_with_pattern(session_name, "exit", "bye!", 5)
                logger.info("Closing tmux session...")
                subprocess.run(f'tmux kill-session -t {session_name}', shell=True, check=True)
                return
        else:
            excess = balance - total_with_fees
            logger.info(f"✅ SUFFICIENT BALANCE! About {excess:.8f} {network_config['currency_symbol']} will remain after transfers.")
            
            confirm = input("Do you want to proceed with transfers? (y/n): ").strip().lower()
            if confirm != 'y':
                logger.info("Operation cancelled by user.")
                logger.info("Closing Kaspa CLI...")
                tmux_send_command_with_pattern(session_name, "exit", "bye!", 5)
                logger.info("Closing tmux session...")
                subprocess.run(f'tmux kill-session -t {session_name}', shell=True, check=True)
                return
        
        # Perform transfers
        successful_transfers = 0
        failed_transfers = 0
        error_details = []  # List to store error details
        
        for i, (address, amount) in enumerate(transfers):
            logger.info(f"[{i+1}/{len(transfers)}] Sending {amount} {network_config['currency_symbol']} to {address}")
            
            # Send transfer command
            send_output = tmux_send_command_with_pattern(session_name, f"send {address} {amount}", "Enter wallet password:")
            if send_output is None:
                error_msg = "Error sending transfer command"
                logger.error(f"❌ {error_msg}")
                error_details.append(f"Transfer #{i+1}: {error_msg}")
                failed_transfers += 1
                continue
            
            # Enter wallet password
            wallet_password_output = tmux_send_command_with_pattern(session_name, wallet_password, "Enter payment password:", password=True)
            if wallet_password_output is None:
                error_msg = "Error entering wallet password"
                logger.error(f"❌ {error_msg}")
                error_details.append(f"Transfer #{i+1}: {error_msg}")
                failed_transfers += 1
                continue
            
            # Enter payment password
            payment_output = tmux_send_command_with_pattern(session_name, payment_password, "Send - Amount:", password=True)
            
            # Check if transfer was successful
            output_cmd = f'tmux capture-pane -p -t {session_name}'
            output = subprocess.run(output_cmd, shell=True, check=True, stdout=subprocess.PIPE).stdout.decode('utf-8')
            
            if "Sending" in output and "tx ids:" in output:
                # Try to extract transaction ID
                tx_id = extract_transaction_id(output)
                
                if tx_id:
                    logger.info(f"✅ Transfer successful: {amount} {network_config['currency_symbol']} → {address} (TX ID: {tx_id})")
                else:
                    logger.info(f"✅ Transfer successful: {amount} {network_config['currency_symbol']} → {address}")
                successful_transfers += 1
            else:
                # Detailed error analysis
                error_msg = "Unknown error"
                if "not enough funds" in output:
                    error_msg = "Insufficient funds"
                    logger.error(f"❌ Transfer failed: {error_msg} - stopping transfers")
                    error_details.append(f"Transfer #{i+1}: {error_msg}")
                    failed_transfers += 1
                    break
                elif "invalid address" in output:
                    error_msg = "Invalid address"
                elif "network error" in output:
                    error_msg = "Network error"
                elif "error" in output.lower():
                    # Try to extract error message
                    try:
                        error_lines = [line for line in output.split('\n') if "error" in line.lower()]
                        if error_lines:
                            error_msg = error_lines[0].strip()
                    except:
                        pass
                
                logger.error(f"❌ Transfer failed: {amount} {network_config['currency_symbol']} → {address} - {error_msg}")
                logger.debug(f"Error details:\n{output}")
                error_details.append(f"Transfer #{i+1}: {error_msg}")
                failed_transfers += 1
            
            # Short pause between transfers
            time.sleep(3)
        
        # Display transfer summary
        logger.info(f"Transfer summary: {successful_transfers} successful, {failed_transfers} failed")
        
        # Display error details if any
        if error_details:
            logger.info("Details of encountered errors:")
            for error in error_details:
                logger.info(f"  - {error}")
        
        # Get new balance
        new_balance = get_wallet_balance(session_name, network_config["currency_symbol"])
        if new_balance is not None:
            spent = balance - new_balance
            logger.info(f"Final balance: {new_balance} {network_config['currency_symbol']} (amount spent: {spent} {network_config['currency_symbol']})")
        
        # Close CLI and tmux session
        logger.info("Closing Kaspa CLI...")
        tmux_send_command_with_pattern(session_name, "exit", "bye!", 5)
        logger.info("Closing tmux session...")
        subprocess.run(f'tmux kill-session -t {session_name}', shell=True, check=True)
        
        logger.info(f"Script finished. Operation log available in {LOG_FILENAME}")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        logger.exception("Error details:")
        
        # Cleanup attempt in case of error
        try:
            if 'session_name' in locals():
                subprocess.run(f'tmux kill-session -t {session_name}', shell=True, check=True)
        except:
            pass

if __name__ == "__main__":
    logger.info("=== Starting Kaspa transfer automation script ===")
    automate_kaspa_transfers()
