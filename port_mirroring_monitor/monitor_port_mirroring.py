#!/usr/bin/env python3
"""
Port Mirroring Monitor Web Application

This application monitors port mirroring sessions on a network device by:
1. Connecting via SSH to the device
2. Retrieving port-mirroring configuration
3. Monitoring interface traffic counters
4. Validating mirroring effectiveness
5. Displaying results in real-time on a web interface
"""

import re
import json
import time
import threading
from datetime import datetime
from flask import Flask, render_template, jsonify
from Class_SSH_Con import SSH_Conn
import argparse
import sys
import logging

app = Flask(__name__)

# Global variables for monitoring
monitoring_data = {
    'sessions': {},
    'last_update': None,
    'status': 'Disconnected',
    'error': None
}

class PortMirroringMonitor:
    def __init__(self, host, username='dnroot', password='dnroot'):
        self.host = host
        self.username = username
        self.password = password
        self.ssh_conn = None
        self.monitoring = False
        
    def connect(self):
        """Establish SSH connection to the device"""
        try:
            # Create authentication list
            auth_list = [[self.username, self.password]]
            
            # Initialize SSH connection
            self.ssh_conn = SSH_Conn(
                host=self.host,
                authentication=auth_list,
                session_log='filename',  # No session logging
                icmp_test=True,
                reconnect=True
            )
            
            # Connect to the device
            self.ssh_conn.connect()
            
            if self.ssh_conn.get_status():
                print(f"Successfully connected to {self.host}")
                return True
            else:
                print(f"Failed to connect to {self.host}")
                return False
                
        except Exception as e:
            print(f"Connection error: {str(e)}")
            return False
    
    def disconnect(self):
        """Disconnect from the device"""
        if self.ssh_conn:
            try:
                self.ssh_conn.disconnect()
                print("Disconnected from device")
            except Exception as e:
                print(f"Disconnect error: {str(e)}")
    
    def get_port_mirroring_config(self):
        """Retrieve port mirroring configuration from the device"""
        try:
            if not self.ssh_conn or not self.ssh_conn.get_status():
                raise Exception("SSH connection not established")
            
            # Execute command to get port mirroring configuration
            cmd = "sh conf services port-mirroring | flatten"
            output = self.ssh_conn.exec_command(cmd, timeout=30)
            
            if not output:
                raise Exception("No output received from port mirroring command")
            
            return self.parse_port_mirroring_config(output)
            
        except Exception as e:
            raise Exception(f"Failed to get port mirroring config: {str(e)}")
    
    def parse_port_mirroring_config(self, config_output):
        """Parse port mirroring configuration to extract sessions"""
        sessions = {}
        
        # Split output into lines
        lines = config_output.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            
            # Look for session definitions
            if 'services port-mirroring session' in line:
                parts = line.split()
                
                if len(parts) >= 4:  # Ensure we have enough parts
                    session_name = parts[3]
                    
                    if 'admin-state enabled' in line:
                        # Extract session name
                        if session_name not in sessions:
                            sessions[session_name] = {
                                'name': session_name,
                                'admin_state': 'enabled',
                                'source_interfaces': [],
                                'destination_interface': None,
                                'description': None
                            }
                    
                    elif 'destination-interface' in line and len(parts) >= 6:
                        # Extract destination interface - it's parts[5] not parts[4]
                        dest_interface = parts[5]
                        if session_name not in sessions:
                            sessions[session_name] = {
                                'name': session_name,
                                'admin_state': 'unknown',
                                'source_interfaces': [],
                                'destination_interface': None,
                                'description': None
                            }
                        sessions[session_name]['destination_interface'] = dest_interface
                    
                    elif 'source-interface' in line and len(parts) >= 6:
                        # Extract source interface - it's parts[5] not parts[4]
                        source_interface = parts[5]
                        
                        # Parse direction - look for 'direction' keyword and get the next part
                        direction = 'both'  # default
                        if 'direction' in parts:
                            dir_index = parts.index('direction')
                            if dir_index + 1 < len(parts):
                                next_part = parts[dir_index + 1]
                                # Handle valid direction values, default to 'both' for invalid ones
                                if next_part in ['ingress', 'egress', 'both']:
                                    direction = next_part
                                else:
                                    direction = 'both'  # Default for invalid/truncated values
                        
                        if session_name not in sessions:
                            sessions[session_name] = {
                                'name': session_name,
                                'admin_state': 'unknown',
                                'source_interfaces': [],
                                'destination_interface': None,
                                'description': None
                            }
                        sessions[session_name]['source_interfaces'].append({
                            'interface': source_interface,
                            'direction': direction
                        })
                    
                    elif 'description' in line and len(parts) >= 6:
                        # Extract description - everything after 'description'
                        desc_index = parts.index('description')
                        if desc_index + 1 < len(parts):
                            description = ' '.join(parts[desc_index + 1:])
                            if session_name not in sessions:
                                sessions[session_name] = {
                                    'name': session_name,
                                    'admin_state': 'unknown',
                                    'source_interfaces': [],
                                    'destination_interface': None,
                                    'description': None
                                }
                            sessions[session_name]['description'] = description
        
        return sessions
    
    def get_interface_counters(self, interface):
        """Get traffic counters for a specific interface"""
        try:
            if not self.ssh_conn or not self.ssh_conn.get_status():
                raise Exception("SSH connection not established")
            
            # Execute command to get interface counters
            cmd = f'sh interfaces counters {interface} | inc regex "^\\s*(RX|TX) octets:"'
            output = self.ssh_conn.exec_command(cmd, timeout=15)
            
            if not output:
                return {'rx_mbps': 0.0, 'tx_mbps': 0.0, 'rx_octets': 0, 'tx_octets': 0}
            
            return self.parse_interface_counters(output)
            
        except Exception as e:
            print(f"Failed to get counters for {interface}: {str(e)}")
            return {'rx_mbps': 0.0, 'tx_mbps': 0.0, 'rx_octets': 0, 'tx_octets': 0}
    
    def parse_interface_counters(self, counter_output):
        """Parse interface counter output to extract traffic rates"""
        counters = {'rx_mbps': 0.0, 'tx_mbps': 0.0, 'rx_octets': 0, 'tx_octets': 0}
        
        lines = counter_output.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            
            if 'RX octets:' in line:
                # Extract RX Mbps: "RX octets: 12948298 ( 217 bps / 0.0 Mbps)"
                match = re.search(r'RX octets:\s+(\d+)\s+\([^/]*\/\s*([\d.]+)\s*Mbps\)', line)
                if match:
                    counters['rx_octets'] = int(match.group(1))
                    counters['rx_mbps'] = float(match.group(2))
            
            elif 'TX octets:' in line:
                # Extract TX Mbps: "TX octets: 3259646366958 ( 376 bps / 0.0 Mbps)"
                match = re.search(r'TX octets:\s+(\d+)\s+\([^/]*\/\s*([\d.]+)\s*Mbps\)', line)
                if match:
                    counters['tx_octets'] = int(match.group(1))
                    counters['tx_mbps'] = float(match.group(2))
        
        return counters
    
    def validate_mirroring_session(self, session_data, source_counters, dest_counters):
        """Validate mirroring effectiveness by comparing source and destination traffic"""
        validation_results = []
        
        for source_info in session_data['source_interfaces']:
            source_interface = source_info['interface']
            direction = source_info['direction']
            
            # Get source traffic based on direction
            if direction == 'both':
                # For 'both' direction, mirror captures RX + TX traffic
                source_traffic = source_counters[source_interface]['rx_mbps'] + source_counters[source_interface]['tx_mbps']
                source_direction = f'RX+TX (both: {source_counters[source_interface]["rx_mbps"]:.2f}+{source_counters[source_interface]["tx_mbps"]:.2f})'
            elif direction == 'ingress':
                source_traffic = source_counters[source_interface]['rx_mbps']
                source_direction = 'RX (ingress only)'
            elif direction == 'egress':
                source_traffic = source_counters[source_interface]['tx_mbps']
                source_direction = 'TX (egress only)'
            else:
                # Default to both directions for unknown direction types
                source_traffic = source_counters[source_interface]['rx_mbps'] + source_counters[source_interface]['tx_mbps']
                source_direction = f'RX+TX (default: {source_counters[source_interface]["rx_mbps"]:.2f}+{source_counters[source_interface]["tx_mbps"]:.2f})'
            
            # Get destination traffic (mirrored traffic appears on TX)
            dest_interface = session_data['destination_interface']
            dest_traffic = dest_counters[dest_interface]['tx_mbps']
            
            # Validate mirroring effectiveness
            status = "✅"
            message = ""
            
            if source_traffic <= 0.1 and dest_traffic <= 0.1:
                status = "✅"
                message = "Idle & consistent"
            elif source_traffic <= 0.1 and dest_traffic > 0.1:
                status = "⚠️"
                message = f"Source idle but destination has {dest_traffic:.2f} Mbps"
            elif source_traffic > 0.1 and dest_traffic <= 0.1:
                status = "❌"
                message = f"Source has {source_traffic:.2f} Mbps but destination is idle"
            else:
                # Calculate percentage difference
                diff_percent = abs(source_traffic - dest_traffic) / source_traffic * 100 if source_traffic > 0 else 0
                
                if diff_percent <= 10:
                    status = "✅"
                    message = f"Match ({diff_percent:.1f}% delta)"
                else:
                    status = "⚠️"
                    message = f"High delta ({diff_percent:.1f}%)"
            
            validation_results.append({
                'source_interface': source_interface,
                'source_direction': source_direction,
                'source_traffic': source_traffic,
                'dest_interface': dest_interface,
                'dest_traffic': dest_traffic,
                'status': status,
                'message': message,
                'direction': direction
            })
        
        return validation_results
    
    def monitor_sessions(self):
        """Main monitoring function that gathers and validates all port mirroring sessions"""
        global monitoring_data
        
        try:
            # Get port mirroring configuration
            sessions = self.get_port_mirroring_config()
            
            if not sessions:
                monitoring_data['error'] = "No port mirroring sessions found"
                monitoring_data['status'] = "No Sessions"
                return
            
            # Get interface counters for all interfaces
            all_interfaces = set()
            for session in sessions.values():
                if session['destination_interface']:
                    all_interfaces.add(session['destination_interface'])
                for source in session['source_interfaces']:
                    all_interfaces.add(source['interface'])
            
            # Collect counters for all interfaces
            source_counters = {}
            dest_counters = {}
            
            for interface in all_interfaces:
                counters = self.get_interface_counters(interface)
                source_counters[interface] = counters
                dest_counters[interface] = counters
            
            # Validate each session
            session_results = {}
            for session_name, session_data in sessions.items():
                if session_data['destination_interface'] and session_data['source_interfaces']:
                    validation_results = self.validate_mirroring_session(
                        session_data, source_counters, dest_counters
                    )
                    
                    session_results[session_name] = {
                        'config': session_data,
                        'validation': validation_results,
                        'source_counters': {src['interface']: source_counters[src['interface']] 
                                          for src in session_data['source_interfaces']},
                        'dest_counters': {session_data['destination_interface']: 
                                        dest_counters[session_data['destination_interface']]}
                    }
            
            # Update global monitoring data
            monitoring_data['sessions'] = session_results
            monitoring_data['last_update'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            monitoring_data['status'] = 'Connected'
            monitoring_data['error'] = None
            
        except Exception as e:
            monitoring_data['error'] = str(e)
            monitoring_data['status'] = 'Error'
            print(f"Monitoring error: {str(e)}")

# Global monitor instance
monitor = None

def monitoring_loop(host, interval):
    """Background monitoring loop"""
    global monitor, monitoring_data
    
    monitor = PortMirroringMonitor(host)
    
    while True:
        try:
            if not monitor.ssh_conn or not monitor.ssh_conn.get_status():
                monitoring_data['status'] = 'Connecting...'
                if monitor.connect():
                    monitoring_data['status'] = 'Connected'
                else:
                    monitoring_data['status'] = 'Connection Failed'
                    monitoring_data['error'] = 'Failed to establish SSH connection'
                    time.sleep(interval)
                    continue
            
            # Perform monitoring
            monitor.monitor_sessions()
            
        except Exception as e:
            monitoring_data['error'] = str(e)
            monitoring_data['status'] = 'Error'
            print(f"Monitoring loop error: {str(e)}")
            
            # Try to reconnect
            try:
                if monitor.ssh_conn:
                    monitor.disconnect()
                time.sleep(2)
            except:
                pass
        
        time.sleep(interval)

@app.route('/')
def index():
    """Main page route"""
    return render_template('index.html')

@app.route('/api/data')
def get_data():
    """API endpoint to get current monitoring data"""
    return jsonify(monitoring_data)

@app.route('/api/status')
def get_status():
    """API endpoint to get current status"""
    return jsonify({
        'status': monitoring_data['status'],
        'last_update': monitoring_data['last_update'],
        'error': monitoring_data['error']
    })

# HTML template content (will be saved separately)
HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Port Mirroring Monitor</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background-color: white;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            padding: 30px;
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 2px solid #e0e0e0;
        }
        .header h1 {
            color: #333;
            margin-bottom: 10px;
        }
        .status-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 5px;
            font-weight: bold;
        }
        .status-connected { background-color: #d4edda; color: #155724; }
        .status-error { background-color: #f8d7da; color: #721c24; }
        .status-connecting { background-color: #fff3cd; color: #856404; }
        .status-disconnected { background-color: #f8d7da; color: #721c24; }
        
        .session-card {
            border: 1px solid #ddd;
            border-radius: 8px;
            margin-bottom: 20px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }
        .session-header {
            background-color: #007bff;
            color: white;
            padding: 15px;
            font-weight: bold;
            font-size: 18px;
        }
        .session-content {
            padding: 20px;
        }
        .validation-item {
            display: flex;
            align-items: center;
            padding: 12px;
            margin-bottom: 10px;
            border-radius: 5px;
            border-left: 4px solid #007bff;
        }
        .validation-success {
            background-color: #d4edda;
            border-left-color: #28a745;
        }
        .validation-warning {
            background-color: #fff3cd;
            border-left-color: #ffc107;
        }
        .validation-error {
            background-color: #f8d7da;
            border-left-color: #dc3545;
        }
        .status-icon {
            font-size: 20px;
            margin-right: 15px;
        }
        .interface-info {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-top: 15px;
        }
        .interface-box {
            border: 1px solid #e0e0e0;
            border-radius: 5px;
            padding: 15px;
            background-color: #f8f9fa;
        }
        .interface-title {
            font-weight: bold;
            color: #495057;
            margin-bottom: 10px;
        }
        .counter-row {
            display: flex;
            justify-content: space-between;
            margin-bottom: 5px;
        }
        .counter-label {
            color: #6c757d;
        }
        .counter-value {
            font-weight: bold;
            color: #495057;
        }
        .traffic-rate {
            color: #007bff;
            font-weight: bold;
        }
        .no-sessions {
            text-align: center;
            color: #6c757d;
            font-style: italic;
            padding: 40px;
        }
        .loading {
            text-align: center;
            padding: 40px;
        }
        .error-message {
            background-color: #f8d7da;
            color: #721c24;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
            border: 1px solid #f5c6cb;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 Port Mirroring Monitor</h1>
            <p>Real-time monitoring of network port mirroring sessions</p>
        </div>
        
        <div id="status-bar" class="status-bar status-connecting">
            <span id="status-text">Connecting...</span>
            <span id="last-update">Last Update: Never</span>
        </div>
        
        <div id="error-container"></div>
        
        <div id="content">
            <div class="loading">
                <p>🔄 Loading port mirroring data...</p>
            </div>
        </div>
    </div>

    <script>
        function updateDisplay() {
            fetch('/api/data')
                .then(response => response.json())
                .then(data => {
                    updateStatusBar(data);
                    updateContent(data);
                })
                .catch(error => {
                    console.error('Error fetching data:', error);
                    updateStatusBar({ status: 'Error', error: 'Failed to fetch data' });
                });
        }

        function updateStatusBar(data) {
            const statusBar = document.getElementById('status-bar');
            const statusText = document.getElementById('status-text');
            const lastUpdate = document.getElementById('last-update');
            
            // Update status
            statusText.textContent = `Status: ${data.status}`;
            lastUpdate.textContent = `Last Update: ${data.last_update || 'Never'}`;
            
            // Update status bar class
            statusBar.className = 'status-bar';
            switch(data.status) {
                case 'Connected':
                    statusBar.classList.add('status-connected');
                    break;
                case 'Error':
                case 'Connection Failed':
                    statusBar.classList.add('status-error');
                    break;
                case 'Connecting...':
                    statusBar.classList.add('status-connecting');
                    break;
                default:
                    statusBar.classList.add('status-disconnected');
            }
        }

        function updateContent(data) {
            const content = document.getElementById('content');
            const errorContainer = document.getElementById('error-container');
            
            // Clear previous error
            errorContainer.innerHTML = '';
            
            // Show error if present
            if (data.error) {
                errorContainer.innerHTML = `
                    <div class="error-message">
                        <strong>Error:</strong> ${data.error}
                    </div>
                `;
            }
            
            // Update main content
            if (!data.sessions || Object.keys(data.sessions).length === 0) {
                content.innerHTML = '<div class="no-sessions">No port mirroring sessions found</div>';
                return;
            }
            
            let html = '';
            for (const [sessionName, sessionData] of Object.entries(data.sessions)) {
                html += generateSessionCard(sessionName, sessionData);
            }
            content.innerHTML = html;
        }

        function generateSessionCard(sessionName, sessionData) {
            const config = sessionData.config;
            const validations = sessionData.validation;
            const sourceCounters = sessionData.source_counters;
            const destCounters = sessionData.dest_counters;
            
            let validationHtml = '';
            for (const validation of validations) {
                const statusClass = validation.status === '✅' ? 'validation-success' : 
                                  validation.status === '⚠️' ? 'validation-warning' : 'validation-error';
                
                validationHtml += `
                    <div class="validation-item ${statusClass}">
                        <span class="status-icon">${validation.status}</span>
                        <div>
                            <strong>${validation.source_interface} → ${validation.dest_interface}</strong><br>
                            Source ${validation.source_direction}: ${validation.source_traffic.toFixed(2)} Mbps | 
                            Dest TX: ${validation.dest_traffic.toFixed(2)} Mbps<br>
                            <em>${validation.message}</em>
                        </div>
                    </div>
                `;
            }
            
            // Generate interface counters HTML
            let interfaceHtml = '<div class="interface-info">';
            
            // Source interfaces
            for (const [interface, counters] of Object.entries(sourceCounters)) {
                interfaceHtml += `
                    <div class="interface-box">
                        <div class="interface-title">📥 Source: ${interface}</div>
                        <div class="counter-row">
                            <span class="counter-label">RX:</span>
                            <span class="counter-value">${counters.rx_octets.toLocaleString()} octets</span>
                        </div>
                        <div class="counter-row">
                            <span class="counter-label">TX:</span>
                            <span class="counter-value">${counters.tx_octets.toLocaleString()} octets</span>
                        </div>
                        <div class="counter-row">
                            <span class="counter-label">Rate:</span>
                            <span class="traffic-rate">RX: ${counters.rx_mbps} Mbps | TX: ${counters.tx_mbps} Mbps</span>
                        </div>
                    </div>
                `;
            }
            
            // Destination interface
            for (const [interface, counters] of Object.entries(destCounters)) {
                interfaceHtml += `
                    <div class="interface-box">
                        <div class="interface-title">📤 Destination: ${interface}</div>
                        <div class="counter-row">
                            <span class="counter-label">RX:</span>
                            <span class="counter-value">${counters.rx_octets.toLocaleString()} octets</span>
                        </div>
                        <div class="counter-row">
                            <span class="counter-label">TX:</span>
                            <span class="counter-value">${counters.tx_octets.toLocaleString()} octets</span>
                        </div>
                        <div class="counter-row">
                            <span class="counter-label">Rate:</span>
                            <span class="traffic-rate">RX: ${counters.rx_mbps} Mbps | TX: ${counters.tx_mbps} Mbps</span>
                        </div>
                    </div>
                `;
            }
            
            interfaceHtml += '</div>';
            
            return `
                <div class="session-card">
                    <div class="session-header">
                        Session: ${sessionName}
                        ${config.description ? ` - ${config.description}` : ''}
                    </div>
                    <div class="session-content">
                        ${validationHtml}
                        ${interfaceHtml}
                    </div>
                </div>
            `;
        }

        // Initial load and set up auto-refresh
        updateDisplay();
        setInterval(updateDisplay, 5000); // Refresh every 5 seconds
    </script>
</body>
</html>'''

def create_template_file():
    """Create the HTML template file"""
    import os
    templates_dir = os.path.join(os.path.dirname(__file__), 'templates')
    os.makedirs(templates_dir, exist_ok=True)
    
    template_path = os.path.join(templates_dir, 'index.html')
    with open(template_path, 'w') as f:
        f.write(HTML_TEMPLATE)
    
    print(f"Created template file: {template_path}")

def main():
    parser = argparse.ArgumentParser(description='Port Mirroring Monitor Web Application')
    parser.add_argument('--host', required=True, help='Hostname or IP address of the device')
    parser.add_argument('--port', type=int, default=8080, help='Web server port (default: 8080)')
    parser.add_argument('--interval', type=int, default=5, help='Monitoring interval in seconds (default: 5)')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--rediscover', type=int, default=0, help='Rediscover interval (legacy parameter, ignored)')
    
    args = parser.parse_args()
    
    # Create template file
    create_template_file()
    
    # Start monitoring thread
    monitoring_thread = threading.Thread(
        target=monitoring_loop, 
        args=(args.host, args.interval),
        daemon=True
    )
    monitoring_thread.start()
    
    # Configure logging
    if not args.debug:
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)
    
    print(f"Starting Port Mirroring Monitor...")
    print(f"Device: {args.host}")
    print(f"Web interface: http://localhost:{args.port}")
    print(f"Monitoring interval: {args.interval} seconds")
    print(f"Press Ctrl+C to stop")
    
    try:
        app.run(host='0.0.0.0', port=args.port, debug=args.debug, threaded=True)
    except KeyboardInterrupt:
        print("\nShutting down...")
        if monitor:
            monitor.disconnect()
        sys.exit(0)

if __name__ == '__main__':
    main() 




