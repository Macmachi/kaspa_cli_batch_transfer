# Kaspa Batch Transfer Tool Documentation

This documentation explains how the Kaspa batch transfer script works and provides instructions for installing the Kaspa CLI wallet on Linux.

## Table of Contents

1. [Script Overview](#script-overview)
2. [What's New in v1.3.0](#whats-new-in-v130)
3. [How the Script Works](#how-the-script-works)
4. [Installing Kaspa CLI Wallet on Linux](#installing-kaspa-cli-wallet-on-linux)
5. [Using the Script](#using-the-script)
6. [Redistribution File Format](#redistribution-file-format)
7. [Troubleshooting](#troubleshooting)
8. [Example Workflow](#example-workflow)
   
---

## Script Overview

The `kaspa_batch.py` script is a tool for automating batch transfers of Kaspa (KAS) cryptocurrency through the Kaspa CLI wallet. It allows you to process multiple transactions from a single wallet to multiple recipients, supports both mainnet and testnet, and handles all CLI interactions automatically.

### Key Features

- **Multi-wallet support:** Detects and lists all available wallets, allowing you to select which one to use.
- Support for both mainnet and testnet networks.
- **Transaction verification:** Verifies transfers through the Kaspa REST API.
- **Retry mechanism:** Automatically retries transfers that initially fail with "Insufficient funds" errors.
- Detailed logging of all operations (see the `logs` directory).
- Balance checking before transfers.
- Secure password handling.
- Error handling and reporting.

---

## What's New in v1.3.0

**Improved Transaction Reliability and Verification!**
- Added API integration with `https://api.kaspa.org` to verify transaction receipt.
- Implemented retry mechanism for "Insufficient funds" errors.
- Increased transaction verification timeout for more reliable confirmations.
- More robust transaction detection to minimize false negatives.
- Automatic creation of "pending transactions" file for any unconfirmed transfers.
- Default wallet "kaspa" is automatically selected if it's the only wallet.

---

## How the Script Works

The script automates batch Kaspa transfers by the following steps:

1. **Reading a redistribution file** containing addresses and amounts.
2. **Validating addresses and amounts** for safety.
3. **Calculating the total amount** (including an estimation for fees).
4. **Detecting and listing all wallets** in your Kaspa CLI wallet directory.
5. **Allowing you to choose the desired wallet** interactively.
6. **Authenticating** with your wallet/password (supports different payment password if needed).
7. **Checking the selected wallet's balance**.
8. **Performing all transfers one by one** with error handling and feedback.
9. **Verifying each transaction** through the Kaspa API to confirm receipt.
10. **Logging all actions and results** to the `logs` directory.

**Technical Implementation:**

- Uses `tmux` to interact with the Kaspa CLI in a detached session.
- Connects to the Kaspa REST API to verify transactions reached their destination.
- Automates CLI prompts, handles password entry securely, and adapts to CLI output using pattern matching.
- Implements exponential backoff for transaction verification attempts.
- Gives detailed log feedback in both terminal and log files.

---

## Installing Kaspa CLI Wallet on Linux

Follow these steps to install it on your Linux system:

1. **Install prerequisites:**
   ```bash
   sudo apt update
   sudo apt install tmux
   sudo apt install cargo  # If Rust is not already installed
   ```

2. **Build the CLI wallet:**
   ```bash
   git clone https://github.com/kaspanet/rusty-kaspa.git
   cd rusty-kaspa
   cargo build --release -p kaspa-cli
   ```

3. **Run the CLI wallet:**
   ```
   cd cli
   cargo run --release
   ```

4. **Create one or more wallets (first time only):**
   ⚠️ IMPORTANT: Wallet passwords should not contain special characters to avoid technical issues with the script.
   
   ```
   >> network mainnet
   >> connect wss://anna.kaspa.stream/kaspa/mainnet/wrpc/borsh
   >> create
   ```

   - Pick a **unique wallet name/label** every time you create a wallet in the CLI.
   - You can create as many wallets as you want (for hot wallets, cold wallets, etc.).
   - The script will detect them and allow you to choose during transfer.

---

## Using the Script

1. **Prepare your redistribution file** (see below for format).
2. **Make sure you have built and initialized at least one wallet in the Kaspa CLI.**
3. **Run the script:**
   ```bash
   python3 kaspa_batch.py
   ```

4. **Follow the interactive prompts:**
   - Select network (`mainnet`/`testnet`)
   - Choose one of your wallets from the detected list
   - Enter the wallet and payment passwords (securely, after wallet selection)
   - Confirm transfer if balance is sufficient

5. **Check logs**:
   - Results and logs can be found in the `logs/` directory.
   - If any transfers are pending verification, a `pending_transactions_TIMESTAMP.txt` file will be created.

---

## Redistribution File Format

Your `redistribution.txt` file should look like this:

```
Address,Amount
kaspa:qxyz...abc1,10.5
kaspa:qxyz...def2,5.25
kaspa:qxyz...ghi3,1.75
End of redistribution report
```

- You may omit the `kaspa:` or `kaspatest:` prefix; the script will add it as appropriate for the selected network.
- **Amounts must be positive numbers**.
- Addresses incompatible with the selected network are ignored (with a warning in the logs).
- Any lines with invalid format or data are ignored (also logged).

---

## Troubleshooting

**Common Issues:**

- "**tmux is not installed**":  
  Install it using `sudo apt install tmux`.

- "**Unable to retrieve wallet balance**":  
  Make sure you're connected to the correct network and using the correct password for the chosen wallet.

- "**Insufficient balance**":  
  Fund your wallet if you want all transfers to succeed, or allow partial transfers when prompted.

- "**No wallets detected**":  
  Ensure you have created at least one wallet in Kaspa CLI; otherwise, the script will use the default `"kaspa"` wallet.

- "**Passwords with special characters**":
  Avoid using special characters in your passwords as they can cause issues with the script's interaction with the CLI and may not be properly deciphered.

- "**Transfer failures**":  
  See the log file (`logs/`) for detailed errors: invalid addresses, insufficient funds, password issues, or network timeouts.

- "**API connectivity issues**":
  If the script cannot connect to the Kaspa API for transaction verification, check your internet connection and try again.

### Log Files:
The script creates log files in the `logs` directory with detailed information about each run. These logs can be valuable for troubleshooting issues.

---

## Example Workflow

```text
$ python3 kaspa_batch.py
Choose network (mainnet/testnet): mainnet
📋 Getting available wallets...
📂 Available wallets:
  1. kaspa
  2. wallet2
  3. wallet3
Choose wallet (1-3): 2

🔑 Entering wallet credentials:
Enter wallet password:
Enter payment password (leave empty if same):

💰 Current balance: 58.43008834 KAS
Estimated total with fees: 15.75006108 KAS
Do you want to proceed with transfers? (y/n): y

📤 Starting transfers...
[1/3] Sending 10.5 KAS to kaspa:qxyz...abc1
⏳ Vérifiant la réception de 10.5 KAS par kaspa:qxyz...abc1...
✅ Transaction vérifiée: 10.5 KAS → kaspa:qxyz...abc1 (TX ID: ...)
[2/3] Sending 5.25 KAS to kaspa:qxyz...def2
⏳ Vérifiant la réception de 5.25 KAS par kaspa:qxyz...def2...
✅ Transaction vérifiée: 5.25 KAS → kaspa:qxyz...def2 (TX ID: ...)
[3/3] Sending 1.75 KAS to kaspa:qxyz...ghi3
⏳ Vérifiant la réception de 1.75 KAS par kaspa:qxyz...ghi3...
✅ Transaction vérifiée: 1.75 KAS → kaspa:qxyz...ghi3 (TX ID: ...)

📊 Transfer summary: 3 successful, 0 pending, 0 failed

Closing Kaspa CLI...
Closing tmux session...

✅ Script finished. Operation log available in logs/kaspa_transfers_YYYYMMDD_HHMMSS.log
```
