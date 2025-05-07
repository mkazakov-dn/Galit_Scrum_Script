# Network Automation with Cursor AI

This repository contains tools for automating network device configuration using SSH. The main component is `Class_SSH_Con.py`, which provides a simple way to connect to and configure network devices.

## Quick Start

1. Make sure you have Python installed on your system
2. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

## How to Use Cursor AI for Network Automation

### Basic Steps to Create a New Script

1. **Open Cursor AI** and create a new Python file (e.g., `my_network_script.py`)

2. **Start with the Basic Structure**:
   ```python
   from Class_SSH_Con import SSH_Conn
   import logging
   import os

   # Configure logging
   logging.basicConfig(
       level=logging.INFO,
       format='%(asctime)s - %(levelname)s - %(message)s'
   )
   logger = logging.getLogger(__name__)
   ```

3. **Tell Cursor AI What You Want to Do**
   - Be specific about your requirements
   - List the steps in order
   - Mention any specific commands you want to run
   - Example: "I want to connect to these devices, enter config mode, and run these commands..."

4. **Let Cursor AI Help You**
   - Cursor AI will use `Class_SSH_Con.py` to implement your requirements
   - It will create the necessary code structure
   - It will handle SSH connections and command execution

### Example Requirements Format

When asking Cursor AI to help you, structure your request like this:

```
I need to:
1. Connect to these devices: [list of device serials]
2. Enter configuration mode
3. Run these commands: [list of commands]
4. Commit the changes
5. Show the results
```

### Important Features to Know About

1. **Session Logging**
   - Each device connection creates a log file
   - Log files are named `{device_serial}_ssh_log`
   - Useful for troubleshooting

2. **Error Handling**
   - The code automatically handles connection issues
   - Failed commands are logged
   - Connections are properly closed

3. **Command Execution**
   - Commands can be executed in show mode or config mode
   - Changes can be committed with a custom name
   - Output can be displayed or saved

### Example Scripts

1. **Basic Configuration** (`example_usage.py`)
   - Shows how to connect to devices
   - Demonstrates command execution
   - Includes session logging
   - Shows how to commit changes

2. **Device Data Collection** (`Devices Serials/run_sn_commands.py`)
   - Shows how to collect data from multiple devices
   - Demonstrates parsing command output
   - Includes error handling

### Tips for Working with Cursor AI

1. **Be Specific**
   - List exact commands you want to run
   - Specify the order of operations
   - Mention any special requirements

2. **Use Examples**
   - Reference existing scripts like `example_usage.py`
   - Point to specific parts you want to modify
   - Show the format of commands you want to use

3. **Ask for Clarification**
   - If Cursor AI's response isn't what you expected, ask for changes
   - Request simpler code if needed
   - Ask for more comments or explanations

### Common Tasks

1. **Connecting to Devices**
   ```python
   ssh = SSH_Conn(host="device_serial", icmp_test=False)
   ssh.connect()
   ```

2. **Entering Config Mode**
   ```python
   ssh.change_mode(ssh.SSH_ENUMS.CLI_MODE.DNOS_CFG)
   ```

3. **Running Commands**
   ```python
   ssh.exec_command("your command here")
   ```

4. **Committing Changes**
   ```python
   ssh.commit_cfg(commit_name="your_commit_name")
   ```

5. **Showing Results**
   ```python
   ssh.change_mode(ssh.SSH_ENUMS.CLI_MODE.DNOS_SHOW)
   output = ssh.exec_command("show command")
   ```

## Need Help?

1. Look at the example scripts in this repository
2. Check the session logs for troubleshooting
3. Ask Cursor AI to explain any part of the code
4. Request modifications to match your specific needs

Remember: Cursor AI is here to help you automate your network tasks. The more specific you are about your requirements, the better it can assist you!