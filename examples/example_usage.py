#!/usr/bin/env python3
from Class_SSH_Con import SSH_Conn
import logging
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def configure_devices():
    # List of device serial numbers to configure
    devices = [
        "WNG1C7VS00017P2",
        "WDY1CBV400005",
        "WK31BC7B00001B2"
    ]

    # Commands to execute
    commands = [
        "system netconf vrf mgmt0 admin-state enabled client-list 0.0.0.0/0",
        "system netconf vrf mgmt0 client-list type allow",
        "system ssh server vrf mgmt0 admin-state enabled client-list 0.0.0.0/0"
    ]

    # Process each device
    for serial in devices:
        try:
            # Create a unique log file for each device's SSH session
            # This will create files like: WNG1C7VS00017P2_ssh_log, WDY1CBV400005_ssh_log, etc.
            log_file = os.path.join(os.getcwd(), f'{serial}_ssh_lo_ALPHA')
            logger.info(f"Creating session log file: {log_file}")
            
            # Connect to device with session logging enabled
            logger.info(f"Connecting to {serial}")
            ssh = SSH_Conn(
                host=serial,
                icmp_test=False,
                session_log=log_file  # This enables detailed SSH session logging
            )
            ssh.connect()
            
            # Enter config mode and execute commands
            ssh.change_mode(ssh.SSH_ENUMS.CLI_MODE.DNOS_CFG)
            for cmd in commands:
                ssh.exec_command(cmd)
            
            # Commit and show results
            ssh.commit_cfg(commit_name="netconf_ssh_config")
            ssh.change_mode(ssh.SSH_ENUMS.CLI_MODE.DNOS_SHOW)
            
            # Show netconf configuration
            print(f"\nNetconf configuration for {serial}:")
            print("=" * 50)
            print(ssh.exec_command("show system netconf"))
            print("=" * 50)
            
        except Exception as e:
            logger.error(f"Error with {serial}: {str(e)}")
            
        finally:
            try:
                ssh.disconnect()
            except:
                pass

if __name__ == "__main__":
    configure_devices() 