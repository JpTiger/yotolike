#!/usr/bin/env python3
"""
Enhanced RFID Musical Box with Rotary Encoder Volume Control - FIXED VERSION
- Rotary encoder on GPIO 26 (CLK), GPIO 16 (DT), GPIO 13 (SW)
- Volume control via encoder rotation
- Pause/Resume via encoder button press
- RFID tag detection for song selection
- Supports both WAV and MP3 files
- Proper GPIO mode configuration and shutdown handling
"""

import time
from time import sleep
import pygame
import sys
import RPi.GPIO as GPIO
from mfrc522 import SimpleMFRC522
import re
import os
import signal
import threading

class RotaryEncoder:
    def __init__(self, clk_pin, dt_pin, sw_pin):
        """Initialize rotary encoder with BCM GPIO numbers"""
        self.clk_pin = clk_pin  # GPIO 26
        self.dt_pin = dt_pin    # GPIO 16
        self.sw_pin = sw_pin    # GPIO 13
        
        # Set up GPIO pins with proper pull-ups
        GPIO.setup(self.clk_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(self.dt_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(self.sw_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        
        # Track previous states
        self.clk_last_state = GPIO.input(self.clk_pin)
        self.dt_last_state = GPIO.input(self.dt_pin)
        self.sw_last_state = GPIO.input(self.sw_pin)
        
        self.last_button_time = 0
        self.last_rotation_time = 0
        self.rotation_counter = 0
        
        # Wait a moment for pins to stabilize
        time.sleep(0.1)
        
        print(f"🔧 Encoder setup - CLK: GPIO{self.clk_pin}, DT: GPIO{self.dt_pin}, SW: GPIO{self.sw_pin}")
        print(f"🔧 Initial states - CLK: {self.clk_last_state}, DT: {self.dt_last_state}, SW: {self.sw_last_state}")
    
    def check_rotation(self):
        """Check for encoder rotation and return direction (1, -1, or 0)"""
        current_time = time.time()
        
        # Read current states
        clk_state = GPIO.input(self.clk_pin)
        dt_state = GPIO.input(self.dt_pin)
        
        # Check if CLK pin has changed (falling edge detection)
        if clk_state != self.clk_last_state and clk_state == 0:  # Falling edge
            # Debounce check
            if current_time - self.last_rotation_time > 0.005:
                # Determine direction based on DT state when CLK goes low
                if dt_state == 0:
                    direction = -1   # Counter-clockwise
                else:
                    direction = 1  # Clockwise
                
                self.last_rotation_time = current_time
                self.rotation_counter += 1
                
                print(f"🔄 Rotation #{self.rotation_counter}: {direction} (CLK: {clk_state}, DT: {dt_state})")
                
                # Update states
                self.clk_last_state = clk_state
                self.dt_last_state = dt_state
                return direction
        
        # Update states even if no rotation detected
        self.clk_last_state = clk_state
        self.dt_last_state = dt_state
        return 0
    
    def check_button(self):
        """Check for button press and return True if pressed"""
        current_time = time.time()
        sw_state = GPIO.input(self.sw_pin)
        
        # Detect falling edge (button press)
        if sw_state == 0 and self.sw_last_state == 1:
            # Debounce check
            if current_time - self.last_button_time > 0.3:
                self.last_button_time = current_time
                self.sw_last_state = sw_state
                print("🔘 Button pressed!")
                return True
        
        self.sw_last_state = sw_state
        return False

class MusicBox:
    def __init__(self):
        self.reader = SimpleMFRC522()
        self.current_text = "Start"
        self.volume = 0.7  # Start at 70% volume
        self.is_paused = False
        self.is_playing = False
        self.running = True
        self.shutdown_requested = False
        
        # Initialize pygame mixer with better settings for Pi Zero
        try:
            pygame.mixer.pre_init(frequency=22050, size=-16, channels=2, buffer=1024)
            pygame.mixer.init()
            pygame.mixer.music.set_volume(self.volume)
            print("✅ Audio system initialized")
        except Exception as e:
            print(f"❌ Audio initialization failed: {e}")
            raise
        
        # Set up rotary encoder with BCM GPIO numbers
        try:
            self.encoder = RotaryEncoder(
                clk_pin=26,  # GPIO 26 (Physical pin 37)
                dt_pin=16,   # GPIO 16 (Physical pin 36)
                sw_pin=13    # GPIO 13 (Physical pin 33)
            )
            print("✅ Rotary encoder initialized")
        except Exception as e:
            print(f"❌ Encoder initialization failed: {e}")
            raise
        
        # Set up signal handlers for clean shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        print("\n🎵 RFID Musical Box with Volume Control Ready!")
        print("- Place RFID tag to play music")
        print("- Rotate encoder to adjust volume")
        print("- Press encoder button to pause/resume")
        print("- Press Ctrl-C to stop")
        print("- Supports WAV and MP3 files")
        print(f"- Current volume: {int(self.volume * 100)}%")
        print("-" * 50)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        print(f"\n🛑 Received signal {signum}, initiating graceful shutdown...")
        self.shutdown_requested = True
        self.running = False
    
    def handle_volume_change(self, direction):
        """Handle volume change from rotary encoder"""
        # Adjust volume in 5% increments
        volume_step = 0.05
        
        if direction > 0:  # Clockwise - increase volume
            new_volume = min(1.0, self.volume + volume_step)
        else:  # Counter-clockwise - decrease volume
            new_volume = max(0.0, self.volume - volume_step)
        
        # Only update if volume actually changed
        if new_volume != self.volume:
            self.volume = new_volume
            pygame.mixer.music.set_volume(self.volume)
            
            # Visual feedback
            volume_percent = int(self.volume * 100)
            volume_bar = "█" * (volume_percent // 5) + "░" * (20 - (volume_percent // 5))
            print(f"🔊 Volume: {volume_percent:3d}% [{volume_bar}]")
    
    def handle_pause_resume(self):
        """Handle pause/resume from rotary encoder button"""
        if self.is_playing:
            if self.is_paused:
                pygame.mixer.music.unpause()
                self.is_paused = False
                print("▶️  Music resumed")
            else:
                pygame.mixer.music.pause()
                self.is_paused = True
                print("⏸️  Music paused")
        else:
            print("❌ No music currently playing")
    
    def play_character_song(self, character_name):
        """Play the song for the given character - supports WAV and MP3"""
        try:
            # Try both WAV and MP3 extensions
            base_path = f"/home/joel/musicbox/{character_name}"
            
            for ext in ['.wav', '.mp3']:
                filepath = base_path + ext
                if os.path.exists(filepath):
                    print(f"\n🎵 Loading: {character_name}")
                    print(f"📁 File: {filepath}")
                    
                    # Stop current music first
                    if pygame.mixer.music.get_busy():
                        pygame.mixer.music.stop()
                        time.sleep(0.1)  # Brief pause to ensure stop completes
                    
                    pygame.mixer.music.load(filepath)
                    pygame.mixer.music.set_volume(self.volume)
                    pygame.mixer.music.play()
                    
                    self.is_playing = True
                    self.is_paused = False
                    
                    print(f"🔊 Playing {character_name} at {int(self.volume * 100)}% volume")
                    return True
            
            # If we get here, no file was found
            print(f"❌ No audio file found for {character_name} (.wav or .mp3)")
            return False
            
        except pygame.error as e:
            print(f"❌ Error loading {character_name}: {e}")
            return False
        except Exception as e:
            print(f"❌ Unexpected error playing {character_name}: {e}")
            return False
    
    def check_music_status(self):
        """Check if music is still playing and update status"""
        if self.is_playing and not self.is_paused:
            if not pygame.mixer.music.get_busy():
                print("🎵 Song finished")
                self.is_playing = False
                self.is_paused = False
    
    def run(self):
        """Main loop for RFID detection with encoder polling"""
        try:
            rfid_check_time = 0
            status_check_time = 0
            loop_count = 0
            
            print("🚀 Starting main loop...")
            
            while self.running and not self.shutdown_requested:
                current_time = time.time()
                loop_count += 1
                
                # Check encoder rotation (high priority)
                try:
                    rotation = self.encoder.check_rotation()
                    if rotation != 0:
                        self.handle_volume_change(rotation)
                except Exception as e:
                    print(f"⚠️  Encoder rotation error: {e}")
                
                # Check encoder button (high priority)
                try:
                    if self.encoder.check_button():
                        self.handle_pause_resume()
                except Exception as e:
                    print(f"⚠️  Encoder button error: {e}")
                
                # Check music status every second
                if current_time - status_check_time > 1.0:
                    self.check_music_status()
                    status_check_time = current_time
                
                # Check RFID every 0.5 seconds to avoid blocking encoder
                if current_time - rfid_check_time > 0.5:
                    try:
                        # Quick RFID read with timeout
                        tag_id, text = self.reader.read_no_block()
                        
                        if tag_id is not None and text and text.strip():
                            text = text.strip()
                            print(f"\n🔍 Tag detected - ID: {tag_id}")
                            print(f"📝 Text: '{text}'")
                            
                            # Check if it's the same character and music is still playing
                            if (text == self.current_text and 
                                pygame.mixer.music.get_busy() and 
                                not self.is_paused):
                                print("🔄 Same character already playing, continuing...")
                            else:
                                # Extract character name (letters only)
                                character = "".join(re.findall("[a-zA-Z]+", text))
                                
                                if character:
                                    if self.play_character_song(character):
                                        self.current_text = text
                                else:
                                    print("⚠️  No valid character name found in tag")
                        
                        rfid_check_time = current_time
                        
                    except Exception as e:
                        print(f"⚠️  RFID read error: {e}")
                        rfid_check_time = current_time
                
                # Debug output every 5000 loops (less frequent)
                if loop_count % 5000 == 0:
                    clk = GPIO.input(26)
                    dt = GPIO.input(16)
                    sw = GPIO.input(13)
                    print(f"🔍 Loop {loop_count} - Encoder states: CLK:{clk} DT:{dt} SW:{sw}")
                
                # Small delay to prevent excessive CPU usage
                time.sleep(0.002)  # 2ms delay
                    
        except KeyboardInterrupt:
            print("\n👋 Keyboard interrupt received...")
        except Exception as e:
            print(f"❌ Unexpected error in main loop: {e}")
        finally:
            print("🛑 Main loop ended, starting cleanup...")
            self.cleanup()
    
    def cleanup(self):
        """Clean up resources properly"""
        print("🧹 Starting cleanup process...")
        self.running = False
        
        # Stop any playing music
        try:
            if pygame.mixer.get_init() and pygame.mixer.music.get_busy():
                print("🎵 Stopping music...")
                pygame.mixer.music.stop()
                time.sleep(0.1)
        except Exception as e:
            print(f"⚠️  Music stop error: {e}")
        
        # Clean up pygame
        try:
            if pygame.mixer.get_init():
                pygame.mixer.quit()
                print("✅ Pygame audio cleanup complete")
        except Exception as e:
            print(f"⚠️  Pygame cleanup error: {e}")
        
        # Clean up GPIO
        try:
            GPIO.cleanup()
            print("✅ GPIO cleanup complete")
        except Exception as e:
            print(f"⚠️  GPIO cleanup error: {e}")
        
        print("✅ Cleanup complete - application terminated safely")

def main():
    """Main function with proper error handling"""
    # Set GPIO mode to BCM and disable warnings
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)  # Use BCM numbering
    
    print("🎵 RFID Musical Box Starting...")
    print("🔧 GPIO mode set to BCM")
    
    try:
        musicbox = MusicBox()
        musicbox.run()
    except KeyboardInterrupt:
        print("\n👋 Application interrupted by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("🧹 Final GPIO cleanup...")
        GPIO.cleanup()
        print("👋 Application ended")

if __name__ == "__main__":
    main()
