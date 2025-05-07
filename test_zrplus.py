#!/usr/bin/env python3
import csv
import re
import time
from datetime import datetime
from Class_SSH_Con import SSH_Conn

# Constants
SERIAL = "WNG1C7VS00017P2"        # single device for now
IF_A = "ge400-0/0/27"            # first interface
IF_B = "ge400-0/0/28"            # second interface
WAIT_SECS = 120                   # 2-minute settle time
CSV_OUT = "zrplus_results.csv"

def verify_interface_state(ssh, interface):
    """Verify if interface is up by checking physical link state"""
    cmd = "show interface {} | inc Physical".format(interface)
    output = ssh.exec_command(cmd)
    return "Physical link state: up" in output

def discover_parameters(ssh, interface):
    """Discover supported grid spacing, frequency range, and TX power range"""
    cmd = "show interfaces transceiver {} | inc supported".format(interface)
    output = ssh.exec_command(cmd)
    
    # Parse grid spacing values
    grid_match = re.search(r'Grid spacing:\s+([\d\.]+GHz(?:,\s*[\d\.]+GHz)*)', output)
    if not grid_match:
        raise ValueError("Could not find grid spacing values")
    grids = [g.strip() for g in grid_match.group(1).split(',')]
    
    # Parse frequency range
    freq_match = re.search(r'Frequency range:\s+([\d\.]+)THz\s*-\s*([\d\.]+)THz', output)
    if not freq_match:
        raise ValueError("Could not find frequency range")
    freq_range = (float(freq_match.group(1)), float(freq_match.group(2)))
    
    # Parse TX power range
    tx_match = re.search(r'TX power range:\s+([-\d\.]+)dBm\s*-\s*([-\d\.]+)dBm', output)
    if not tx_match:
        raise ValueError("Could not find TX power range")
    tx_range = (float(tx_match.group(1)), float(tx_match.group(2)))
    
    return grids, freq_range, tx_range

def configure_interface(ssh, interface, grid, freq_mhz, tx_power):
    """Configure interface with given parameters"""
    cmds = [
        "configure",
        "interfaces {} transceiver optical-transport grid-spacing {}".format(interface, grid),
        "interfaces {} transceiver optical-transport center-frequency {} mhz".format(interface, freq_mhz),
        "interfaces {} transceiver optical-transport target-output-power {}".format(interface, tx_power),
        "top",
        "commit log auto_zr_test"
    ]
    
    for cmd in cmds:
        ssh.exec_command(cmd)

def main():
    # Initialize SSH connection
    ssh = SSH_Conn(host=SERIAL, icmp_test=False)
    ssh.connect()
    
    try:
        # Verify both interfaces are up
        if not verify_interface_state(ssh, IF_A) or not verify_interface_state(ssh, IF_B):
            print("Error: One or both interfaces are down")
            return 1
        
        # Discover parameters on IF_A
        grids, freq_range, tx_range = discover_parameters(ssh, IF_A)
        
        # Create CSV file with header if it doesn't exist
        try:
            with open(CSV_OUT, 'x') as f:
                writer = csv.writer(f)
                writer.writerow(['timestamp', 'grid', 'freq_thz', 'tx_dbm', 'IF_A_state', 'IF_B_state'])
        except FileExistsError:
            pass
        
        # Test each combination
        for grid in grids:
            # Calculate test frequencies
            start_thz, end_thz = freq_range
            low_freq = start_thz + 0.1
            mid_freq = (start_thz + end_thz) / 2
            high_freq = end_thz - 0.1
            
            # Calculate test TX powers
            min_tx, max_tx = tx_range
            low_tx = min_tx
            mid_tx = (min_tx + max_tx) / 2
            high_tx = max_tx
            
            # Test all combinations
            for freq in [low_freq, mid_freq, high_freq]:
                for tx in [low_tx, mid_tx, high_tx]:
                    # Convert frequency to MHz
                    freq_mhz = int(freq * 1000000)
                    
                    # Configure both interfaces
                    configure_interface(ssh, IF_A, grid, freq_mhz, tx)
                    configure_interface(ssh, IF_B, grid, freq_mhz, tx)
                    
                    # Wait for settle time
                    time.sleep(WAIT_SECS)
                    
                    # Check interface states
                    if_a_state = "Up" if verify_interface_state(ssh, IF_A) else "Down"
                    if_b_state = "Up" if verify_interface_state(ssh, IF_B) else "Down"
                    
                    # Write results to CSV
                    with open(CSV_OUT, 'a') as f:
                        writer = csv.writer(f)
                        writer.writerow([
                            datetime.now().isoformat(),
                            grid,
                            freq,
                            tx,
                            if_a_state,
                            if_b_state
                        ])
        
        print("✔ done, results in {}".format(CSV_OUT))
        return 0
        
    finally:
        ssh.disconnect()

if __name__ == "__main__":
    exit(main())