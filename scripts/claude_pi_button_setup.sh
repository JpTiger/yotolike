#!/bin/bash
# Complete setup for Pi Zero W button wake/shutdown - CORRECTED VERSION

echo "=== Raspberry Pi Button Setup (Software-Only Version) ==="

# 1. Remove any existing gpio-shutdown overlay and configure for wake-only
CONFIG_FILE="/boot/firmware/config.txt"
if [ ! -f "$CONFIG_FILE" ]; then
    # Fallback to old location for compatibility
    CONFIG_FILE="/boot/config.txt"
fi

echo "Configuring wake-only setup in $CONFIG_FILE..."

# Remove any existing gpio-shutdown overlays
sudo sed -i '/dtoverlay=gpio-shutdown/d' "$CONFIG_FILE"

# Add wake-only configuration - GPIO 3 can wake without overlay
sudo tee -a "$CONFIG_FILE" << 'EOF'

# Button wake configuration (software shutdown handling)
# GPIO 3 will automatically wake from halt (built-in Pi feature)
# No overlay needed - Python script handles shutdown logic
EOF

# 2. Create shutdown script - CORRECTED VERSION
echo "Creating shutdown monitoring script..."
sudo tee /usr/local/bin/button-shutdown.py << 'EOF'
#!/usr/bin/env python3
"""
Button shutdown monitor for Raspberry Pi
Monitors GPIO 4 for shutdown signal
Compatible with Raspberry Pi OS Bookworm
SOFTWARE-ONLY VERSION - correct NC button logic (HIGH = pressed)
"""
import RPi.GPIO as GPIO
import time
import subprocess
import logging
import signal
import sys
import os

# Configuration
SHUTDOWN_PIN = 4
DEBOUNCE_TIME = 0.1  # 100ms debounce
HOLD_TIME = 2.0     # Require 2 second hold to prevent accidental shutdown

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/var/log/button-shutdown.log')
    ]
)
logger = logging.getLogger(__name__)

def signal_handler(sig, frame):
    """Handle shutdown signals gracefully"""
    logger.info("Received shutdown signal, cleaning up...")
    GPIO.cleanup()
    sys.exit(0)

def shutdown_system():
    """Initiate system shutdown"""
    logger.info("Shutdown button held - initiating shutdown...")
    try:
        subprocess.run(['/usr/bin/sudo', '/usr/sbin/shutdown', '-h', 'now'], check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to initiate shutdown: {e}")

def main():
    # Check if we're running as root
    if os.geteuid() != 0:
        logger.error("This script must be run as root")
        sys.exit(1)
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Setup GPIO - use BCM numbering
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)  # Suppress warnings in Bookworm
    
    try:
        # Setup pin with pull-up resistor (NC contact normally connects to ground)
        GPIO.setup(SHUTDOWN_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        
        # Log initial state
        initial_state = GPIO.input(SHUTDOWN_PIN)
        logger.info(f"Button monitoring started. GPIO {SHUTDOWN_PIN} initial state: {initial_state}")
        logger.info("Waiting for button press (NC contact opening, GPIO going HIGH)...")
        
        # Continuous monitoring loop
        while True:
            try:
                # Check current button state
                current_state = GPIO.input(SHUTDOWN_PIN)
                
                # If button is pressed (NC contact opens, GPIO goes HIGH)
                if current_state == GPIO.HIGH:
                    logger.info("Button press detected, checking hold time...")
                    
                    # Wait and verify it's held for the required time
                    hold_start = time.time()
                    button_held = True
                    
                    while (time.time() - hold_start) < HOLD_TIME:
                        if GPIO.input(SHUTDOWN_PIN) == GPIO.LOW:
                            logger.info("Button released before hold time, ignoring")
                            button_held = False
                            break
                        time.sleep(0.1)  # Check every 100ms
                    
                    if button_held and GPIO.input(SHUTDOWN_PIN) == GPIO.HIGH:
                        shutdown_system()
                        break
                    
                # Small delay to prevent excessive CPU usage
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(1)  # Wait before retrying
                
    except Exception as e:
        logger.error(f"Fatal error in GPIO setup: {e}")
        sys.exit(1)
    finally:
        logger.info("Cleaning up GPIO...")
        GPIO.cleanup()

if __name__ == "__main__":
    main()
EOF

# 3. Make script executable
sudo chmod +x /usr/local/bin/button-shutdown.py

# 4. Create systemd service
echo "Creating systemd service..."
sudo tee /etc/systemd/system/button-shutdown.service << 'EOF'
[Unit]
Description=Button Shutdown Monitor
After=multi-user.target
Wants=multi-user.target

[Service]
Type=simple
ExecStart=/usr/local/bin/button-shutdown.py
Restart=always
RestartSec=5
RestartPreventExitStatus=0
User=root
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# 5. Stop existing service if running
sudo systemctl stop button-shutdown.service 2>/dev/null || true

# 6. Enable service
echo "Enabling button-shutdown service..."
sudo systemctl daemon-reload
sudo systemctl enable button-shutdown.service

# 7. Install Python GPIO and ensure system compatibility
echo "Installing required packages for Bookworm..."
sudo apt update
sudo apt install -y python3-rpi.gpio python3-lgpio

# Enable GPIO access for non-root users (Bookworm requirement)
if ! groups $USER | grep -q gpio; then
    echo "Adding $USER to gpio group..."
    sudo usermod -a -G gpio $USER
fi

# Enable I2C if not already enabled (needed for shared GPIO 3)
if ! grep -q "^dtparam=i2c_arm=on" "$CONFIG_FILE"; then
    echo "dtparam=i2c_arm=on" | sudo tee -a "$CONFIG_FILE"
    echo "I2C enabled in config"
fi

# 8. Test the script setup
echo ""
echo "=== Testing Script Setup ==="
echo "Testing GPIO configuration..."
sudo python3 -c "
import RPi.GPIO as GPIO
import time
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
try:
    GPIO.setup(4, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    state = GPIO.input(4)
    print(f'GPIO 4 current state: {state} (should be HIGH when not pressed)')
    print('Press button for 3 seconds if you want to test...')
    for i in range(30):
        current = GPIO.input(4)
        if current != state:
            print(f'Button state changed to: {current}')
            break
        time.sleep(0.1)
    print('GPIO setup test complete!')
finally:
    GPIO.cleanup()
"

echo ""
echo "=== Setup Complete (Software-Only) ==="
echo "Wiring:"
echo "  Yellow (Common) → Pin 6 (Ground)"
echo "  Blue (NO)       → Pin 5 (GPIO 3) - Wake"  
echo "  Green (NC)      → Pin 7 (GPIO 4) - Shutdown"
echo ""
echo "How it works:"
echo "  - Press button when running: 2-second hold triggers shutdown"
echo "  - Press button when halted: GPIO 3 wakes the system (built-in Pi feature)"
echo "  - No device tree overlay conflicts"
echo ""
echo "IMPORTANT: Reboot required to remove overlay conflicts:"
echo "  sudo reboot"
echo ""
echo "After reboot, check service status:"
echo "  sudo systemctl status button-shutdown.service"
echo ""
echo "To debug issues:"
echo "  sudo journalctl -u button-shutdown.service -f"
echo "  sudo tail -f /var/log/button-shutdown.log"
echo ""
echo "To test manually before service:"
echo "  sudo python3 /usr/local/bin/button-shutdown.py"
echo ""
if [ "$CONFIG_FILE" = "/boot/firmware/config.txt" ]; then
    echo "Note: Using Bookworm config location (/boot/firmware/config.txt)"
fi