#!/usr/bin/env python3
from reduced_module import SSH_Conn

def main():
    # Device connection parameters
    host = 'WDY1CBV400005'  # Replace with your device IP
    interface = 'ge100-0/0/1'  # Replace with your interface
    description = "Test description"

    try:
        # Create SSH connection with logging enabled
        print(f"Connecting to {host}...")
        ssh = SSH_Conn(host=host, session_log='ssh_test.log')
        
        # Connect to the device
        ssh.connect()
        print("Connected successfully!")

        # Get and display system information
        print("\nGetting system information...")
        system_info = ssh.exec_command(cmd="show system", exec_mode=ssh.SSH_ENUMS.EXEC_MODE.SHOW)
        print("System Information:")
        print(system_info)

        # Enter configure mode
        print("\nEntering configure mode...")
        if ssh.change_mode(requested_cli=ssh.SSH_ENUMS.CLI_MODE.DNOS_CFG):
            print("Successfully entered configure mode")

            # Configure interface description
            print(f"\nConfiguring interface {interface}...")
            config_cmd = f'interfaces {interface} description "{description}"'
            ssh.exec_command(cmd=config_cmd, exec_mode=ssh.SSH_ENUMS.EXEC_MODE.CFG)

            # Commit the changes
            print("\nCommitting changes...")
            if ssh.commit_cfg(commit_name="test_interface_config"):
                print("Configuration committed successfully!")
            else:
                print("Failed to commit configuration")

            # Exit configure mode
            print("\nExiting configure mode...")
            ssh.change_mode(requested_cli=ssh.SSH_ENUMS.CLI_MODE.DNOS_SHOW)
        else:
            print("Failed to enter configure mode")

    except Exception as e:
        print(f"An error occurred: {str(e)}")

    finally:
        # Always disconnect
        try:
            ssh.disconnect()
            print("\nDisconnected from device")
        except:
            pass

if __name__ == "__main__":
    main() 