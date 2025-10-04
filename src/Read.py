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

    def is_pressed(self):
        return GPIO.input(self.sw_pin) == 0

class MusicBox:
    def __init__(self):
        self.reader = SimpleMFRC522()
        self.current_text = "Start"  # default label
        # Ensure attribute always exists even before first play
        self.current_text = self.current_text or ""
        self.volume = 0.5  # Start at 50% volume
        self.is_paused = False
        self.is_playing = False
        self.running = True
        self.shutdown_requested = False

        # Playback tracking
        self.current_track_path = None
        self.current_pos_sec = 0.0
        self.last_status_update_time = time.time()
        self.seek_step_sec = 10  # seconds per detent when seeking
        self.paused_uid = None  # track UID that caused a pause due to removal

        # RFID presence debouncing (required for stable presence)
        self.current_uid = None          # UID considered 'present'
        self.uid_last_seen = 0.0         # last time we saw the current UID
        self.remove_grace = 1.0          # seconds with no reads before 'removed'

        # NEW: RFID edge state to avoid replays / pause->restart bugs
        self.last_uid = None     # last seen RFID UID (or None if no card present)
        self.armed = True        # only trigger playback once per card-present cycle
        
        # Initialize pygame mixer
        try:
            pygame.mixer.pre_init(frequency=22050, size=-16, channels=2, buffer=1024)
            pygame.mixer.init()
            pygame.mixer.music.set_volume(self.volume)
            print("✅ Audio system initialized")
            # Startup sound setup
            self.startup_channel = None
            self.startup_sound_path = os.path.join(os.path.dirname(__file__), "startup.mp3")
        except Exception as e:
            print(f"❌ Audio initialization failed: {e}")
            raise
        
        # Set up rotary encoder
        try:
            self.encoder = RotaryEncoder(
                clk_pin=26,
                dt_pin=16,
                sw_pin=13
            )
            print("✅ Rotary encoder initialized")
        except Exception as e:
            print(f"❌ Encoder initialization failed: {e}")
            raise
        
        # Signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        print("\n🎵 RFID Musical Box with Volume Control Ready!")

        # Play startup sound non-blocking, if present
        self.play_startup_sound()
    
    def _signal_handler(self, signum, frame):
        print(f"\n🛑 Received signal {signum}, initiating graceful shutdown.")
        self.shutdown_requested = True
        self.running = False
    
    def handle_volume_change(self, direction):
        volume_step = 0.05
        if direction > 0:
            new_volume = min(1.0, self.volume + volume_step)
        else:
            new_volume = max(0.0, self.volume - volume_step)
        if new_volume != self.volume:
            self.volume = new_volume
            pygame.mixer.music.set_volume(self.volume)
            print(f"🔊 Volume: {int(self.volume*100)}%")
    
    def handle_pause_resume(self):
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
    
    def play_track(self, track_name, start_pos: float = 0.0):
        try:
            # Revert to hardcoded path
            base_path = os.path.join(os.path.dirname(__file__), track_name)
            for ext in ['.wav', '.mp3']:
                filepath = base_path + ext
                if os.path.exists(filepath):
                    if pygame.mixer.music.get_busy():
                        pygame.mixer.music.stop()
                        time.sleep(0.1)
                    pygame.mixer.music.load(filepath)
                    pygame.mixer.music.set_volume(self.volume)
                    # Fade out startup sound if still playing
                    try:
                        if getattr(self, "startup_channel", None) and self.startup_channel.get_busy():
                            self.startup_channel.fadeout(300)
                    except Exception:
                        pass

                    if start_pos and start_pos > 0:
                        try:
                            pygame.mixer.music.play(start=start_pos)
                        except TypeError:
                            pygame.mixer.music.play()
                            pygame.mixer.music.set_pos(start_pos)
                    else:
                        pygame.mixer.music.play()
                    self.is_playing = True
                    self.is_paused = False
                    self.current_track_path = filepath
                    self.current_pos_sec = float(start_pos) if start_pos else 0.0
                    self.last_status_update_time = time.time()
                    print(f"🔊 Playing {track_name} (start={start_pos:.1f}s)")
                    return True
            print(f"❌ No audio file found for {track_name}")
            return False
        except Exception as e:
            print(f"❌ Error playing {track_name}: {e}")
            return False
    
    def check_music_status(self):
        now = time.time()
        if self.is_playing and not self.is_paused and pygame.mixer.music.get_busy():
            delta = now - self.last_status_update_time
            if delta > 0:
                self.current_pos_sec += delta
        self.last_status_update_time = now
        if self.is_playing and not self.is_paused and not pygame.mixer.music.get_busy():
            print("🎵 Song finished")
            self.is_playing = False
    
    def handle_seek(self, direction):
        """Seek within the current track; press + rotate to scrub."""
        if not self.current_track_path:
            print("↔️  Seek ignored (no track loaded)")
            return
        step = self.seek_step_sec * (1 if direction > 0 else -1)
        new_pos = max(0.0, self.current_pos_sec + step)
        was_playing = self.is_playing and not self.is_paused
        was_paused = self.is_paused
        try:
            pygame.mixer.music.stop()
            pygame.mixer.music.load(self.current_track_path)
            pygame.mixer.music.set_volume(self.volume)
            try:
                pygame.mixer.music.play(start=new_pos)
            except TypeError:
                pygame.mixer.music.play()
                pygame.mixer.music.set_pos(new_pos)
            self.current_pos_sec = new_pos
            self.last_status_update_time = time.time()
            if was_paused:
                pygame.mixer.music.pause()
                self.is_paused = True
                self.is_playing = True
                print(f"⏱️  Scrubbed to {new_pos:.1f}s (paused)")
            elif was_playing:
                self.is_playing = True
                self.is_paused = False
                print(f"⏩⏪ Seek to {new_pos:.1f}s")
            else:
                self.is_playing = True
                self.is_paused = False
                print(f"▶️  Restarted at {new_pos:.1f}s after finish")
        except Exception as e:
            print(f"⚠️ Seek error: {e}")

    def play_startup_sound(self):
        try:
            if os.path.exists(self.startup_sound_path):
                snd = pygame.mixer.Sound(self.startup_sound_path)
                snd.set_volume(self.volume)
                self.startup_channel = snd.play()
            else:
                # No startup sound file; skip silently
                pass
        except Exception as e:
            print(f"⚠️ Startup sound error: {e}")

    def run(self):
        try:
            rfid_check_time = 0
            status_check_time = 0
            while self.running and not self.shutdown_requested:
                current_time = time.time()

                direction = self.encoder.check_rotation()
                if direction != 0:
                    if self.encoder.is_pressed():
                        self.handle_seek(direction)
                    else:
                        self.handle_volume_change(direction)
                # Ignore simple button taps for now
                # if self.encoder.check_button(): pass
                if current_time - status_check_time > 1.0:
                    self.check_music_status()
                    status_check_time = current_time
                # RFID edge-triggered logic (debounced)
                if current_time - rfid_check_time > 0.5:
                    try:
                        tag_id, text = self.reader.read_no_block()
                        seen_uid = str(tag_id) if tag_id is not None else None
                        if seen_uid is not None:
                            if self.current_uid is None:
                                # Rising edge: new card detected
                                self.current_uid = str(seen_uid)
                                self.uid_last_seen = current_time
                                # Resume first if this is the same UID we paused on
                                if self.is_paused and self.current_track_path and str(self.paused_uid) == str(seen_uid):
                                    pygame.mixer.music.unpause()
                                    self.is_paused = False
                                    self.is_playing = True
                                    self.last_status_update_time = time.time()
                                    print("▶️  Resumed after reinsert")
                                    self.armed = False
                                else:
                                    print(f"\n💳 Card added/changed: UID={seen_uid}")
                                    if text:
                                        text = text.strip()
                                    track = re.sub(r"[^A-Za-z0-9_-]", "", text or "") if text else ""
                                    if track:
                                        if self.play_track(track, start_pos=0.0):
                                            self.current_text = text
                                            self.paused_uid = None
                                    self.armed = False
                            else:
                                # Card still present; check if changed UID
                                self.uid_last_seen = current_time
                                if str(seen_uid) != str(self.current_uid):
                                    self.current_uid = str(seen_uid)
                                    print(f"\n💳 Card added/changed: UID={seen_uid}")
                                    if text:
                                        text = text.strip()
                                    track = re.sub(r"[^A-Za-z0-9_-]", "", text or "") if text else ""
                                    if track:
                                        if self.play_track(track, start_pos=0.0):
                                            self.current_text = text
                                            self.paused_uid = None
                                        self.armed = False
                        else:
                            # No UID this poll; only consider removal after grace period
                            if self.current_uid is not None and (current_time - self.uid_last_seen) > self.remove_grace:
                                print("💳 Card removed")
                                self.armed = True
                                if self.is_playing and not self.is_paused:
                                    pygame.mixer.music.pause()
                                    self.is_paused = True
                                    # Remember last paused UID (so the same card resumes)
                                    self.paused_uid = str(self.current_uid)
                                    print("⏸️  Paused on card removal")
                                self.current_uid = None
                        rfid_check_time = current_time
                    except Exception as e:
                        print(f"⚠️ RFID read error: {e}")
                        rfid_check_time = current_time
                time.sleep(0.01)
        finally:
            self.cleanup()
    
    def cleanup(self):
        print("🧹 Cleanup starting.")
        try:
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
                pygame.mixer.quit()
        except: pass
        try:
            GPIO.cleanup()
        except: pass
        print("✅ Cleanup complete")

def main():
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    musicbox = MusicBox()
    musicbox.run()

if __name__ == "__main__":
    main()
