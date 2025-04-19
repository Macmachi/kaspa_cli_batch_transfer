# Kaspa Batch Transfer Tool Documentation

This documentation explains how the Kaspa batch transfer script works and provides instructions for installing the Kaspa CLI wallet on Linux.

## Table of Contents

1. [Script Overview](#script-overview)
2. [How the Script Works](#how-the-script-works)
3. [Installing Kaspa CLI Wallet on Linux](#installing-kaspa-cli-wallet-on-linux)
4. [Using the Script](#using-the-script)
5. [Redistribution File Format](#redistribution-file-format)
6. [Troubleshooting](#troubleshooting)

## Script Overview

The `kaspa_batch.py` script is a tool for automating batch transfers of Kaspa (KAS) cryptocurrency through the Kaspa CLI wallet. It allows you to process multiple transactions from a single wallet to multiple recipients in an automated fashion, handling all interaction with the Kaspa CLI.

### Key Features:

- Support for both mainnet and testnet networks
- Detailed logging of all operations
- Balance checking before transfers
- Secure password handling
- Error handling and reporting
- Transaction verification

## How the Script Works

The script operates by:

1. Reading a redistribution file containing addresses and amounts
2. Validating addresses and amounts
3. Calculating the total amount needed (including transaction fees)
4. Checking if the wallet has sufficient balance
5. Automating the Kaspa CLI to perform the transfers
6. Providing detailed reporting of successful and failed transfers

### Technical Implementation:

The script uses `tmux` to create a detached terminal session in which it runs the Kaspa CLI. It then communicates with this session to:

- Initialize the CLI
- Connect to the appropriate network (mainnet or testnet)
- Open the wallet (you have to create one on testnet or mainnet before to start the script!)
- Extract the current balance
- Perform transfers
- Handle errors

The script uses pattern matching to respond to different CLI prompts and accurately track the state of each operation.

## Installing Kaspa CLI Wallet on Linux

The Kaspa CLI wallet is part of the rusty-kaspa project, which is built in Rust. Follow these steps to install it on your Linux system: https://github.com/kaspanet/rusty-kaspa 

### Prerequisites:

1. **Install required package:**

   ```bash
   sudo apt update
   sudo apt install tmux
   ```
2. **Build the CLI wallet:**

   ```bash
   cargo build --release -p kaspa-cli
   ```

   This will compile the CLI wallet into the `target/release` directory.

3. **Run the CLI wallet (for testing the installation):**

   ```bash
   cd cli
   cargo run --release
   ```

   You should see the Kaspa CLI prompt:

   ```
   Welcome to Kaspa CLI!
   Type 'help' for list of commands
   >>
   ```

4. **Create a new wallet (first time only):**

   Within the CLI:

   ```
   >> network mainnet
   >> connect wss://anna.kaspa.stream/kaspa/mainnet/wrpc/borsh
   >> create
   ```

   Follow the prompts to create your wallet, set passwords, and save your seed phrase.

## Using the Script

### Setting Up the Redistribution File:

Create a file named `redistribution.txt` in the same directory as the script with the following format:

```
Address,Amount
kaspa:address1,10.5
kaspa:address2,5.25
kaspa:address3,1.75
End of redistribution report
```

### Running the Script:

1. Make sure your redistribution file is properly formatted and in the same directory as the script.

2. Run the script:

   ```bash
   python3 kaspa_batch.py
   ```

3. Follow the prompts to:
   - Select network (mainnet or testnet)
   - Enter your wallet and payment passwords
   - Confirm transfers

### Reviewing Results:

The script creates a detailed log file in the `logs` directory that you can review to see the results of all operations.

## Redistribution File Format

The redistribution file must follow this specific format:

1. Start with a header line: `Address,Amount`
2. Include one transfer per line with format: `address,amount`
3. End with: `End of redistribution report`

Notes:
- Addresses can be with or without the `kaspa:` or `kaspatest:` prefix
- Amounts must be positive numbers
- The script validates all entries and reports any issues

## Troubleshooting

### Common Issues:

1. **"tmux is not installed"**:
   - Install tmux using: `sudo apt install tmux`

2. **"Unable to retrieve wallet balance"**:
   - Ensure you're connected to the correct network
   - Check that your wallet is properly configured

3. **"Insufficient balance"**:
   - Add funds to your wallet before running the script

4. **Transfer failures**:
   - Check the logs for specific error messages
   - Verify that addresses are correct and valid for the selected network

### Log Files:

The script creates log files in the `logs` directory with detailed information about each run. These logs can be valuable for troubleshooting issues.