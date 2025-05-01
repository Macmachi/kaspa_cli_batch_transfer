# Kaspa Batch Transfer Tool Documentation

This documentation explains how the Kaspa batch transfer script works and provides instructions for installing the Kaspa CLI wallet on Linux.
⚠️ IMPORTANT: Passwords should not contain special characters to avoid technical issues.

## Table of Contents

1. [Script Overview](#script-overview)
2. [What's New in v1.1.0](#whats-new-in-v110)
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
- Detailed logging of all operations (see the `logs` directory).
- Balance checking before transfers.
- Secure password handling.
- Error handling and reporting.
- Transaction verification.

---

## What's New in v1.1.0

**Multi-wallet support!**
- The script detects all available wallets in your Kaspa CLI and lets you choose which wallet to use for your batch transfer.
- If there is only one wallet, it is selected automatically.
- Password prompts only appear after you've selected your wallet.
- Logs contain more granular detail for easier troubleshooting.

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
9. **Logging all actions and results** to the `logs` directory.

**Technical Implementation:**

- Uses `tmux` to interact with the Kaspa CLI in a detached session.
- Automates CLI prompts, handles password entry securely, and adapts to CLI output using pattern matching.
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

- "**Transfer failures**":  
  See the log file (`logs/`) for detailed errors: invalid addresses, insufficient funds, password issues, or network timeouts.

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
[1/3] Sending 10.5 KAS to kaspa:qxyz...abc1
✅ Transfer successful: 10.5 KAS → kaspa:qxyz...abc1 (TX ID: ...)
[2/3] Sending 5.25 KAS to kaspa:qxyz...def2
✅ Transfer successful: 5.25 KAS → kaspa:qxyz...def2 (TX ID: ...)
[3/3] Sending 1.75 KAS to kaspa:qxyz...ghi3
✅ Transfer successful: 1.75 KAS → kaspa:qxyz...ghi3 (TX ID: ...)

📊 Transfer summary: 3 successful, 0 failed

Closing Kaspa CLI...
Closing tmux session...

✅ Script finished. Operation log available in logs/kaspa_transfers_YYYYMMDD_HHMMSS.log
```
