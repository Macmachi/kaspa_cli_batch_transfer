'''
* Author : Rymentz
* Version : v1.3.1

Multi-wallet support:
- The script now detects and lists available wallets
- You can choose which wallet to use for each batch of transfers
- Default wallet "kaspa" is automatically selected if it's the only wallet

Improvements:
- Added retry mechanism for "Insufficient funds" errors
- Increased transaction verification timeout
- More robust transaction detection

Usage:
1. Run the script: python3 kaspa_batch.py
2. Select network (mainnet/testnet)
3. Choose a wallet from the detected list
4. Enter wallet password when prompted
5. Confirm transfers if balance is sufficient

Detailed logs are automatically saved to the logs directory.
'''

import subprocess
import time
import logging
import getpass
import os
import re
import requests
from datetime import datetime

# Ajout de la configuration pour l'API Kaspa
API_BASE_URL = "https://api.kaspa.org"

# Configuration
REDISTRIBUTION_FILE = "redistribution.txt"
# Paramètres pour la vérification des transactions
TRANSACTION_CHECK_INTERVAL = 10  # Vérifier toutes les 10 secondes
TRANSACTION_CHECK_TIMEOUT = 60   # Vérifier pendant 60 secondes maximum
# Paramètres pour les retries de transfert
TRANSFER_RETRY_ATTEMPTS = 3      # Nombre maximum de tentatives
TRANSFER_RETRY_DELAY = 5         # Délai en secondes entre les tentatives

# Log configuration
LOG_DIRECTORY = "logs"
if not os.path.exists(LOG_DIRECTORY):
    os.makedirs(LOG_DIRECTORY)

LOG_FILENAME = os.path.join(LOG_DIRECTORY, f"kaspa_transfers_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

# Configure loggers - one for file (with all details) and one for console (with less details)
# File logger - logs everything including DEBUG messages
file_handler = logging.FileHandler(LOG_FILENAME)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

# Console handler - only logs INFO and above
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(message)s'))

# Configure root logger
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)  # Set to DEBUG to capture all messages
logger.addHandler(file_handler)
logger.addHandler(console_handler)

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

# Fonctions pour vérifier les transactions
def get_transactions(address, limit=50, max_retries=3):
    """Récupère les transactions pour une adresse avec mécanisme de retry."""
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            url = f"{API_BASE_URL}/addresses/{address}/full-transactions"
            params = {
                "limit": limit,
                "resolve_previous_outpoints": "light"
            }
            
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            retry_count += 1
            logger.warning(f"Erreur API (tentative {retry_count}/{max_retries}): {e}")
            if retry_count < max_retries:
                # Backoff exponentiel
                sleep_time = 2 ** retry_count
                time.sleep(sleep_time)
            else:
                logger.error(f"Échec API après {max_retries} tentatives")
                return []
    
    return []

def has_received_exact_amount(address, expected_amount, transactions):
    """
    Vérifie si l'adresse a reçu le montant attendu dans l'une de ses transactions récentes.
    Utilise un arrondi à une décimale et une tolérance pour accommoder les frais.
    """
    try:
        # Convertir le montant attendu
        expected_amount_float = float(expected_amount)
        expected_amount_rounded = round(expected_amount_float, 1)
        
        # Tolérance augmentée pour les frais (0.2 KAS au lieu de 0.1)
        min_acceptable = expected_amount_rounded - 0.2
        
        logger.debug(f"Recherche de paiement pour {address}: attendu {expected_amount_rounded} KAS (min {min_acceptable} KAS)")
        
        for tx in transactions:
            # Ignorer les transactions non acceptées
            if not tx.get("is_accepted", False):
                continue
            
            # Vérifier les sorties de la transaction pour voir si le montant correspond
            for output in tx.get("outputs", []):
                if output.get("script_public_key_address") == address:
                    # Convertir sompi en KAS (1 KAS = 10^8 sompi)
                    received_amount = output.get("amount", 0) / 1e8
                    received_amount_rounded = round(received_amount, 1)
                    
                    logger.debug(f"Montant trouvé: {received_amount_rounded} KAS")
                    
                    # Vérification avec tolérance accrue pour les frais
                    if received_amount_rounded >= min_acceptable and received_amount_rounded <= (expected_amount_rounded + 0.2):
                        logger.debug(f"✅ Montant valide trouvé: {received_amount_rounded} KAS (attendu: {expected_amount_rounded} KAS)")
                        return True
        
        logger.debug(f"❌ Aucun montant valide trouvé pour {address}")
        return False
        
    except Exception as e:
        logger.error(f"Erreur lors de la vérification du montant: {e}")
        return False

def verify_transaction_received(address, amount, max_wait_time=TRANSACTION_CHECK_TIMEOUT, check_interval=TRANSACTION_CHECK_INTERVAL):
    """
    Vérifie périodiquement si la transaction a été reçue par l'adresse cible avec backoff exponentiel.
    Retourne True si la transaction est détectée, False sinon.
    """
    logger.info(f"🔍 Vérifiant la réception de {amount} KAS par {address}...")
    
    # Utiliser un backoff exponentiel pour les vérifications
    current_interval = check_interval
    max_interval = 20  # Intervalle maximum entre les vérifications
    
    end_time = time.time() + max_wait_time
    while time.time() < end_time:
        # Récupérer les transactions récentes de l'adresse
        transactions = get_transactions(address)
        
        # Vérifier si le montant attendu est présent
        if has_received_exact_amount(address, amount, transactions):
            logger.info(f"✅ Transaction vérifiée: {amount} KAS reçus par {address}")
            return True
            
        # Calculer le temps d'attente avec backoff
        sleep_time = min(current_interval, max_interval)
        logger.debug(f"Transaction non détectée, nouvelle vérification dans {sleep_time} secondes...")
        time.sleep(sleep_time)
        current_interval *= 1.5  # Augmentation progressive
    
    logger.warning(f"⚠️ Transaction non détectée après {max_wait_time} secondes pour {address}")
    return False

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

def tmux_send_command_with_pattern(session_name, command, expected_pattern=None, max_wait=30, password=False, success_message=None):
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
    # Handle passwords specially to avoid issues with special characters
    if password:
        # For passwords, we send each character individually to avoid shell interpretation issues
        for char in command:
            char_cmd = f'tmux send-keys -t {session_name} "{char}"'
            subprocess.run(char_cmd, shell=True, check=True)
        # Then send Enter key
        subprocess.run(f'tmux send-keys -t {session_name} Enter', shell=True, check=True)
    else:
        # For regular commands, escape double quotes
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
            
            # Also check for error conditions
            if "Unable to decrypt" in output:
                logger.error("❌ Authentication error: Unable to decrypt")
                found = True  # Consider it found to avoid timeout, we'll handle the error elsewhere
        
        if not found:
            time.sleep(0.5)
    
    # If we didn't find the pattern within the timeout
    if not found:
        logger.warning(f"Pattern '{expected_pattern}' not found within {max_wait}s timeout")
        if success_message:
            # Generate appropriate failure message instead of just replacing symbols
            if "password accepted" in success_message:
                logger.error(f"❌ Authentication failed")
            elif "connected" in success_message.lower():
                logger.error(f"❌ Connection failed")
            else:
                # Generic failure for other cases
                failure_message = success_message.replace('✅', '❌')
                # Remove "successful" or "successfully" from the message if present
                failure_message = failure_message.replace("successfully", "failed to")
                failure_message = failure_message.replace("successful", "failed")
                logger.error(f"{failure_message}")
    else:
        # Log success message if provided
        if success_message:
            logger.info(f"{success_message}")
    
    # Capture final state for debugging (always log to debug level)
    output_cmd = f'tmux capture-pane -p -t {session_name}'
    output = subprocess.run(output_cmd, shell=True, check=True, stdout=subprocess.PIPE).stdout.decode('utf-8')
    logger.debug(f"State after command '{display_cmd}':\n{output}")
    
    return output if found else None

def get_wallet_balance(session_name, currency_symbol):
    """Retrieves the current wallet balance using the 'list' command"""
    # Exécuter la commande 'list' pour afficher les comptes et leurs soldes
    logger.info("Requesting wallet balance information...")
    tmux_send_command_with_pattern(
        session_name,
        "list",
        "$",
        10
    )
    
    # Attendre que le solde s'affiche
    time.sleep(2)
    
    # Capturer la sortie
    output_cmd = f'tmux capture-pane -p -t {session_name}'
    output = subprocess.run(output_cmd, shell=True, check=True, stdout=subprocess.PIPE).stdout.decode('utf-8')
    
    # Log complet pour débogage
    logger.debug(f"Output for balance extraction:\n{output}")
    
    # Plusieurs patterns pour attraper différents formats d'affichage du solde
    # Note: [\d,]+ capture les chiffres avec ou sans virgules comme séparateurs de milliers
    patterns = [
        # Format de la commande list: "w0111 [30d92145]: 6,007 KAS"
        r':\s*([\d,]+(?:\.\d+)?)\s*' + re.escape(currency_symbol),
        # Format standard: "• 123.456 KAS" ou "• 6,007 KAS"
        r'•\s*([\d,]+(?:\.\d+)?)\s*' + re.escape(currency_symbol),
        # Format balance: "Balance: 123.456 KAS"
        r'[Bb]alance[:]?\s*([\d,]+(?:\.\d+)?)\s*' + re.escape(currency_symbol),
        # Format avec parenthèses: "(123.456 KAS)" ou "(6,007 KAS)"
        r'\(\s*([\d,]+(?:\.\d+)?)\s*' + re.escape(currency_symbol) + r'\)',
        # Format générique: tout nombre suivi du symbole de devise
        r'([\d,]+(?:\.\d+)?)\s*' + re.escape(currency_symbol)
    ]
    
    # Essayer chaque pattern
    for pattern in patterns:
        match = re.search(pattern, output)
        if match:
            try:
                balance_str = match.group(1).replace(',', '')
                logger.debug(f"Match found using pattern: {pattern}")
                logger.debug(f"Extracted balance string: {balance_str}")
                return float(balance_str)
            except Exception as e:
                logger.debug(f"Regex match found but conversion error: {e}")
    
    # Si aucun pattern ne fonctionne, essayer avec la commande 'details'
    logger.info("Balance not found with 'list', trying 'details' command...")
    tmux_send_command_with_pattern(
        session_name,
        "details",
        "$",
        10
    )
    
    # Attendre que les infos s'affichent
    time.sleep(2)
    
    # Recapturer la sortie
    output = subprocess.run(output_cmd, shell=True, check=True, stdout=subprocess.PIPE).stdout.decode('utf-8')
    logger.debug(f"Output from 'details' command:\n{output}")
    
    # Réessayer tous les patterns
    for pattern in patterns:
        match = re.search(pattern, output)
        if match:
            try:
                balance_str = match.group(1).replace(',', '')
                return float(balance_str)
            except Exception as e:
                logger.debug(f"Regex match found but conversion error: {e}")
    
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

def get_available_wallets(session_name):
    """Gets a list of available wallets using the wallet list command"""
    logger.info("Retrieving available wallets...")
    
    # Clear any previous output to ensure clean state
    tmux_send_command_with_pattern(
        session_name, 
        "clear", 
        "$", 
        5, 
        success_message="✅ Terminal screen cleared"
    )
    
    # Execute the wallet list command with increased wait time
    print("⏳ Fetching wallet list...")
    logger.info("Executing 'wallet list' command...")
    tmux_send_command_with_pattern(
        session_name, 
        "wallet list", 
        "$", 
        15,
        success_message="✅ Wallet list command executed"
    )
    
    # Wait extra time for the output to fully populate
    time.sleep(3)
    
    # Capture the full output
    output_cmd = f'tmux capture-pane -p -t {session_name}'
    output = subprocess.run(output_cmd, shell=True, check=True, stdout=subprocess.PIPE).stdout.decode('utf-8')
    
    # Log the complete output for debugging (to log file only, not terminal)
    logger.debug(f"Output from 'wallet list' command:\n{output}")
    
    # Parse output to find wallet names
    wallets = []
    
    # First look for the specific pattern shown in the example ("Wallets:" section)
    wallets_section_idx = output.find("Wallets:")
    if wallets_section_idx != -1:
        logger.debug("Found 'Wallets:' section")
        
        # Extract the section between "Wallets:" and the next prompt
        wallets_section = output[wallets_section_idx:]
        if "$" in wallets_section:
            wallets_section = wallets_section.split("$")[0]  # Stop at the next prompt
        
        # Process each line
        for line in wallets_section.split('\n')[1:]:  # Skip the "Wallets:" line
            line = line.strip()
            if not line:
                continue
                
            # Handle the format shown in the example: "  wallet_name: label" or just "  wallet_name"
            if ":" in line:
                wallet_name = line.split(":")[0].strip()
                logger.debug(f"Found wallet with colon format: '{wallet_name}'")
            else:
                wallet_name = line.strip()
                logger.debug(f"Found wallet: '{wallet_name}'")
                
            if wallet_name and wallet_name not in wallets:
                wallets.append(wallet_name)
    
    # If no wallets found, add default kaspa wallet
    if not wallets:
        print("No wallets detected. Using default wallet 'kaspa'")
        logger.warning("No wallets detected. Using default wallet 'kaspa'")
        wallets = ["kaspa"]
    
    print(f"\nDetected wallets: {', '.join(wallets)}")
    logger.info(f"Detected wallets: {', '.join(wallets)}")
    return wallets

def attempt_transfer(session_name, address, amount, wallet_password, payment_password, currency_symbol, max_attempts=TRANSFER_RETRY_ATTEMPTS):
    """Tente d'effectuer un transfert avec plusieurs essais en cas d'erreur 'Insufficient funds'"""
    
    for attempt in range(1, max_attempts + 1):
        if attempt > 1:
            print(f"🔄 Tentative #{attempt} pour transférer {amount} {currency_symbol} vers {address}...")
            logger.info(f"Tentative #{attempt} pour transférer {amount} {currency_symbol} vers {address}")
            
        # Envoi de la commande
        send_output = tmux_send_command_with_pattern(
            session_name, 
            f"send {address} {amount}", 
            "Enter wallet password:",
            success_message=f"✅ Commande de transfert acceptée pour {address}" if attempt == 1 else None
        )
        
        if send_output is None:
            return None, "Erreur d'envoi de commande"
        
        # Mot de passe du portefeuille
        wallet_password_output = tmux_send_command_with_pattern(
            session_name, 
            wallet_password, 
            "Enter payment password:", 
            password=True,
            success_message="✅ Mot de passe portefeuille accepté" if attempt == 1 else None
        )
        
        if wallet_password_output is None:
            return None, "Erreur de mot de passe portefeuille"
        
        # Mot de passe de paiement
        payment_output = tmux_send_command_with_pattern(
            session_name, 
            payment_password, 
            "Send - Amount:", 
            password=True,
            success_message="✅ Mot de passe de paiement accepté" if attempt == 1 else None
        )
        
        # Vérifier le résultat
        output_cmd = f'tmux capture-pane -p -t {session_name}'
        output = subprocess.run(output_cmd, shell=True, check=True, stdout=subprocess.PIPE).stdout.decode('utf-8')
        
        # Si transfert réussi
        if "Sending" in output and "tx ids:" in output:
            tx_id = extract_transaction_id(output)
            return output, None  # Succès
        
        # Si insufficient funds, on réessaie
        elif "Insufficient funds" in output and attempt < max_attempts:
            logger.warning(f"⚠️ Fonds insuffisants pour cette transaction spécifique (tentative {attempt}/{max_attempts})")
            print(f"⚠️ Message 'Insufficient funds' - attente de {TRANSFER_RETRY_DELAY}s avant nouvelle tentative...")
            time.sleep(TRANSFER_RETRY_DELAY)
            continue  # Passer à la prochaine tentative
        
        # Autres erreurs ou dernier essai échoué
        else:
            if "Insufficient funds" in output:
                error_msg = "Fonds insuffisants après plusieurs tentatives"
            elif "invalid address" in output:
                error_msg = "Adresse invalide"
            elif "network error" in output:
                error_msg = "Erreur réseau"
            elif "error" in output.lower():
                try:
                    error_lines = [line for line in output.split('\n') if "error" in line.lower()]
                    if error_lines:
                        error_msg = error_lines[0].strip()
                    else:
                        error_msg = "Erreur inconnue"
                except:
                    error_msg = "Erreur inconnue"
            else:
                error_msg = "Erreur inconnue"
            
            return None, error_msg
    
    return None, "Échec après plusieurs tentatives"

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
        logger.info("✅ Tmux session created successfully")
        
        # Initialize Kaspa CLI
        logger.info("Starting Kaspa CLI...")
        cli_result = tmux_send_command_with_pattern(
            session_name, 
            f"cd ~/rusty-kaspa/cli && cargo run --release", 
            "type 'help' for list of commands", 
            30,
            success_message="✅ Kaspa CLI started successfully"
        )
        if cli_result is None:
            logger.error("❌ Failed to start Kaspa CLI")
            logger.info("Closing tmux session...")
            subprocess.run(f'tmux kill-session -t {session_name}', shell=True, check=True)
            return
        
        # Connect to network
        logger.info(f"Setting network to {network_choice}...")
        network_result = tmux_send_command_with_pattern(
            session_name, 
            network_config["network_cmd"], 
            "Setting network id to:", 
            max_wait=10,
            success_message=f"✅ Network set to {network_choice}"
        )
        if network_result is None:
            logger.error("❌ Failed to set network")
            logger.info("Closing tmux session...")
            subprocess.run(f'tmux kill-session -t {session_name}', shell=True, check=True)
            return
        
        # Connect to Kaspa node with retry logic
        logger.info("Connecting to Kaspa node...")
        max_retries = 3
        retry_count = 0
        connection_successful = False
        
        while retry_count < max_retries and not connection_successful:
            if retry_count > 0:
                logger.warning(f"Retrying connection to Kaspa node (attempt {retry_count+1}/{max_retries})...")
                
            connect_result = tmux_send_command_with_pattern(
                session_name, 
                network_config["connect_cmd"], 
                "Connected to Kaspa node", 
                max_wait=10,
                success_message="✅ Successfully connected to Kaspa node"
            )
            
            if connect_result is not None:
                connection_successful = True
            else:
                retry_count += 1
                if retry_count < max_retries:
                    time.sleep(2)  # Wait before retry
        
        if not connection_successful:
            logger.error("❌ Failed to connect to Kaspa node after 3 attempts")
            logger.info("Closing tmux session...")
            subprocess.run(f'tmux kill-session -t {session_name}', shell=True, check=True)
            return
        
        # Get available wallets - this will now display raw output for debugging
        print("\n✅ Connected to Kaspa node")
        print("\n📋 Getting available wallets...")
        
        available_wallets = get_available_wallets(session_name)
        
        # Print available wallets to console
        print("\n📂 Available wallets:")
        for i, wallet in enumerate(available_wallets):
            print(f"  {i+1}. {wallet}")
        
        # Select wallet
        selected_wallet = None
        if len(available_wallets) == 1:
            selected_wallet = available_wallets[0]
            print(f"\nOnly one wallet available. Automatically selecting: {selected_wallet}")
            logger.info(f"Only one wallet available. Automatically selecting: {selected_wallet}")
        else:
            while True:
                wallet_choice = input(f"\nChoose wallet (1-{len(available_wallets)}): ").strip()
                try:
                    wallet_index = int(wallet_choice) - 1
                    if 0 <= wallet_index < len(available_wallets):
                        selected_wallet = available_wallets[wallet_index]
                        break
                    else:
                        print(f"Please enter a number between 1 and {len(available_wallets)}.")
                except ValueError:
                    print("Please enter a valid number.")
        
        print(f"\n✅ Selected wallet: {selected_wallet}")
        logger.info(f"Selected wallet: {selected_wallet}")
        
        # Request passwords securely AFTER wallet selection
        print("\n🔑 Entering wallet credentials:")
        wallet_password = getpass.getpass("Enter wallet password: ")
        payment_password = getpass.getpass("Enter payment password (leave empty if same): ")
        
        # If payment password is empty, use wallet password
        if not payment_password:
            payment_password = wallet_password
        
        # Open the selected wallet with the correct 'wallet open' command format
        if selected_wallet == "kaspa" or selected_wallet == "default":
            # Use wallet open command with default wallet
            wallet_open_cmd = "wallet open"
        else:
            # Specify the wallet name
            wallet_open_cmd = f"wallet open {selected_wallet}"
        
        print(f"\n🔐 Opening wallet using command: {wallet_open_cmd}")
        logger.info("Opening wallet...")
        wallet_open_result = tmux_send_command_with_pattern(
            session_name, 
            wallet_open_cmd, 
            "Enter wallet password:", 
            15,
            success_message="✅ Wallet opening initiated"
        )
        if wallet_open_result is None:
            logger.error("❌ Failed to open wallet")
            logger.info("Closing tmux session...")
            subprocess.run(f'tmux kill-session -t {session_name}', shell=True, check=True)
            return
            
        logger.info("Entering wallet password...")
        wallet_output = tmux_send_command_with_pattern(
            session_name, 
            wallet_password, 
            "Your wallet hint is:", 
            password=True,
            success_message="✅ Wallet password accepted"
        )
        if wallet_output is None:
            logger.error("❌ Failed to enter wallet password")
            logger.info("Closing tmux session...")
            subprocess.run(f'tmux kill-session -t {session_name}', shell=True, check=True)
            return
        
        # Get wallet balance
        logger.info("Retrieving wallet balance...")
        balance = get_wallet_balance(session_name, network_config["currency_symbol"])
        
        if balance is None:
            logger.error("❌ Unable to retrieve wallet balance")
            logger.info("Closing tmux session...")
            subprocess.run(f'tmux kill-session -t {session_name}', shell=True, check=True)
            logger.info("✅ Tmux session closed successfully")
            return
        
        # Compare balance and total amount
        print(f"\n💰 Current balance: {balance} {network_config['currency_symbol']}")
        logger.info(f"Current balance: {balance} {network_config['currency_symbol']}")
        logger.info(f"✅ Wallet balance retrieved successfully")
        
        if balance < total_with_fees:
            shortfall = total_with_fees - balance
            print(f"\n⚠️ INSUFFICIENT BALANCE! Missing {shortfall:.8f} {network_config['currency_symbol']} to make all transfers.")
            logger.warning(f"⚠️ INSUFFICIENT BALANCE! Missing {shortfall:.8f} {network_config['currency_symbol']} to make all transfers.")
            
            confirm = input("Balance is insufficient. Do you want to continue with possible transfers anyway? (y/n): ").strip().lower()
            if confirm != 'y':
                logger.info("Operation cancelled by user.")
                logger.info("Closing Kaspa CLI...")
                tmux_send_command_with_pattern(
                    session_name, 
                    "exit", 
                    "bye!", 
                    5,
                    success_message="✅ Kaspa CLI closed successfully"
                )
                logger.info("Closing tmux session...")
                subprocess.run(f'tmux kill-session -t {session_name}', shell=True, check=True)
                logger.info("✅ Tmux session closed successfully")
                return
        else:
            excess = balance - total_with_fees
            # Use only one output method to avoid duplication
            print(f"\n✅ SUFFICIENT BALANCE! About {excess:.8f} {network_config['currency_symbol']} will remain after transfers.")
            
            confirm = input("Do you want to proceed with transfers? (y/n): ").strip().lower()
            if confirm != 'y':
                logger.info("Operation cancelled by user.")
                logger.info("Closing Kaspa CLI...")
                tmux_send_command_with_pattern(
                    session_name, 
                    "exit", 
                    "bye!", 
                    5,
                    success_message="✅ Kaspa CLI closed successfully"
                )
                logger.info("Closing tmux session...")
                subprocess.run(f'tmux kill-session -t {session_name}', shell=True, check=True)
                logger.info("✅ Tmux session closed successfully")
                return
        
        # Perform transfers
        print("\n📤 Starting transfers...")
        successful_transfers = 0
        failed_transfers = 0
        pending_transfers = 0  # Transactions qui ont été envoyées mais non confirmées
        error_details = []  # List to store error details
        
        for i, (address, amount) in enumerate(transfers):
            # Use only one output method for transfer start message
            print(f"[{i+1}/{len(transfers)}] Sending {amount} {network_config['currency_symbol']} to {address}")
            
            # Utiliser le mécanisme de retry pour les transferts
            output, error = attempt_transfer(
                session_name, 
                address, 
                amount, 
                wallet_password, 
                payment_password,
                network_config['currency_symbol']
            )
            
            if output is not None:  # Transfert réussi
                # Try to extract transaction ID
                tx_id = extract_transaction_id(output)
                tx_info = f"(TX ID: {tx_id})" if tx_id else ""
                
                # Attendre que la transaction soit confirmée
                print(f"⏳ Vérifiant la réception de {amount} {network_config['currency_symbol']} par {address}...")
                
                # Ajout d'un délai avant de vérifier la transaction
                time.sleep(5)
                
                # Vérifier si la transaction a été reçue
                transaction_confirmed = verify_transaction_received(address, amount)
                
                if transaction_confirmed:
                    print(f"✅ Transaction vérifiée: {amount} {network_config['currency_symbol']} → {address} {tx_info}")
                    logger.info(f"✅ Transaction vérifiée: {amount} {network_config['currency_symbol']} → {address} {tx_info}")
                    successful_transfers += 1
                else:
                    print(f"⚠️ Transaction potentiellement échouée: {amount} {network_config['currency_symbol']} → {address} {tx_info}")
                    logger.warning(f"⚠️ Transaction potentiellement échouée: {amount} {network_config['currency_symbol']} → {address} {tx_info}")
                    error_details.append(f"Transfer #{i+1}: Transaction potentiellement échouée vers {address}")
                    pending_transfers += 1
            else:  # Transfert échoué
                print(f"❌ Échec du transfert: {amount} {network_config['currency_symbol']} → {address} - {error}")
                logger.error(f"❌ Échec du transfert: {amount} {network_config['currency_symbol']} → {address} - {error}")
                error_details.append(f"Transfer #{i+1}: {error}")
                failed_transfers += 1
                
                # Si l'erreur indique un manque de fonds global et non local à la transaction
                if error and "not enough funds" in error.lower() and "Insufficient funds" not in error:
                    print(f"❌ Arrêt des transferts - fonds globalement insuffisants")
                    logger.error(f"❌ Arrêt des transferts - fonds globalement insuffisants")
                    break
            
            # Short pause between transfers
            time.sleep(3)
        
        # Créer un fichier de récupération pour les transactions potentiellement échouées
        if pending_transfers > 0:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            pending_file = f"pending_transactions_{timestamp}.txt"
            
            with open(pending_file, 'w') as f:
                f.write("================================================================================\n")
                f.write("TRANSACTIONS POTENTIELLEMENT ÉCHOUÉES - À VÉRIFIER MANUELLEMENT\n")
                f.write("================================================================================\n")
                f.write("Address,Amount\n")
                
                # Trouver les transactions en attente en utilisant les détails d'erreur
                for error in error_details:
                    if "potentiellement échouée vers" in error:
                        # Extraire l'adresse
                        address_match = re.search(r'échouée vers (kaspa:[a-z0-9]+)', error)
                        if address_match:
                            address = address_match.group(1)
                            # Trouver le montant correspondant
                            for addr, amt in transfers:
                                if addr == address:
                                    f.write(f"{address},{amt}\n")
                
                f.write("\nEnd of redistribution report\n")
            
            print(f"\n⚠️ Un fichier '{pending_file}' a été créé pour les transactions potentiellement échouées.")
            logger.info(f"Fichier '{pending_file}' créé pour les transactions potentiellement échouées.")
        
        # Display transfer summary
        print(f"\n📊 Transfer summary: {successful_transfers} successful, {pending_transfers} pending, {failed_transfers} failed")
        logger.info(f"Transfer summary: {successful_transfers} successful, {pending_transfers} pending, {failed_transfers} failed")
        
        # Display error details if any
        if error_details:
            print("\nDetails of encountered errors:")
            logger.info("Details of encountered errors:")
            for error in error_details:
                print(f"  - {error}")
                logger.info(f"  - {error}")
        
        # Close CLI and tmux session
        print("\nClosing Kaspa CLI...")
        logger.info("Closing Kaspa CLI...")
        tmux_send_command_with_pattern(
            session_name, 
            "exit", 
            "bye!", 
            5, 
            success_message="✅ Kaspa CLI closed successfully"
        )
        print("Closing tmux session...")
        logger.info("Closing tmux session...")
        subprocess.run(f'tmux kill-session -t {session_name}', shell=True, check=True)
        logger.info("✅ Tmux session closed successfully")
        
        print(f"\n✅ Script finished. Operation log available in {LOG_FILENAME}")
        logger.info(f"Script finished. Operation log available in {LOG_FILENAME}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
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