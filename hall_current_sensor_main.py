# Imports
import time
import network
import socket
from machine import Pin, ADC, Timer
import machine
import sys
import wifi_info
import array
import os

###
# Get the ADC stuff ready

# The ADC
adc = ADC(Pin(26))

# Number of elements
N_array = 256;
# The array for storing the values
adc_array = array.array("I", [0] * N_array)
# Current sample
current_sample = 0

# The state of the capture
capture_state = 0
# The old state
old_state = 0

# Number of samples for the pre trigger
N_pre_trigger = 32
# The array for storing the values before the trigger
adc_array_pretrigger = array.array("I", [0] * N_pre_trigger)
# Current sample for the pre trigger
pre_sample = 0
# Pre-trigger state
pretrigger_state = 0
# Trigger high set
trigger_high_set = 24000
# Trigger low set
trigger_low_set = 18000


# The timer routing - when capture_state becomes 1, grab a bunch of samples
def timer_callback(timer):
    global adc, N_array, adc_array, capture_state, old_state, current_sample
    global N_pre_trigger, adc_array_pretrigger, pre_sample, pretrigger_state, trigger_high_set, trigger_low_set
    
    # Check state change
    if (capture_state == 1) & (old_state == 0):
        current_sample = 0
        
    # Save old state
    old_state = capture_state
    
    if capture_state == 1:
        if (current_sample < N_array):
            # Get an ADC sample
            adc_array[current_sample] = adc.read_u16()
            # Increment the current sample
            current_sample = current_sample + 1
        elif (current_sample >= N_array):
            # Set the state
            capture_state = 0            
    else:
        if pretrigger_state == 1:
            # Currently in the pre-trigger state - get ADC sample
            adc_array_pretrigger[pre_sample] = adc.read_u16()
            
            # Check the high and low set
            if (adc_array_pretrigger[pre_sample] > trigger_high_set) | (adc_array_pretrigger[pre_sample] < trigger_low_set):
                capture_state = 1
                pretrigger_state = 0
            else:
                # Keep looping around, capturing samples
                pre_sample = (pre_sample + 1) % N_pre_trigger
                
# The timer
tim = Timer(period = 1, mode = Timer.PERIODIC, callback=timer_callback);

###
# Webserver

# SSID
ssid = wifi_info.ssid
# Wifi password
wifi_password = wifi_info.wifi_password
# IP address
my_ip_addr = '192.168.0.30'

# Please see https://docs.micropython.org/en/latest/library/network.WLAN.html
# Try to connect to WIFI
wlan = network.WLAN(network.STA_IF)
wlan.active(True)

# Specify the IP address
wlan.ifconfig((my_ip_addr, '255.255.255.0', '192.168.4.1', '192.168.4.1'))

# Connect
wlan.connect(ssid, wifi_password)

# Wait for connect or fail
max_wait = 10
while max_wait > 0:
    if wlan.status() < 0 or wlan.status() >= 3:
        break
    max_wait = max_wait - 1
    print('waiting for connection...')    
    time.sleep(1)
    
# Handle connection error
if wlan.status() != 3:
    # Connection to wireless LAN failed
    print('Connection failed')    
    sys.exit()
    
else:
    print('Connected')
    status = wlan.ifconfig()
    print( 'ip = ' + status[0] )
    
# Open socket
addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

# Try to bind the socket
try:
    s.bind(addr)
        
except:
    print('Bind Failed - you might need to wait a minute for things to clear up');    
    sys.exit()
    
# Listen
s.listen(6)
print('listening on', addr)

# Timeout for the socket accept, i.e., s.accept()
s.settimeout(4)

# Listen for connections, serve up web page
while True:
   
    # Handle connection error
    if wlan.status() != 3:
        # Connection to wireless LAN failed
        print('Connection failed during regular operation')
        sys.exit()
        
    # Main loop
    accept_worked = 0
    try:
        print("Run s.accept()")
        cl, addr = s.accept()
        accept_worked = 1
    except:
        print('Timeout waiting on accept - reset the pico if you want to break out of this')
        time.sleep(0.4)
        
    if accept_worked == 1:
        try:
            print('client connected from', addr)
            request = cl.recv(1024)
            print("request:")
            # print(request)
            request = str(request)
            
            # Default response is error message                        
            response = """<HTML><HEAD><TITLE>Error</TITLE></HEAD><BODY>Not found...</BODY></HTML>"""
            
            # Parse the request for the set or get
            done_parse = 0
            
            # Look for request for pretrigger_state
            adc_pre_trig = request.find('?PRETRIGGER_STATE?')
            if adc_pre_trig != -1:
                # Kick off a ADC trigger capture                
                response = str(pretrigger_state)
                done_parse = 1
                
            # Look for request to kick off a triggered ADC capture
            adc_trig = request.find('?PRETRIGGER_STATE=1?')
            if adc_trig != -1:
                # Kick off a ADC trigger capture
                pre_sample = 0
                pretrigger_state = 1
                response = "ok"
                done_parse = 1
                
            # Look for request to get trigger limits
            adc_trig_low = request.find('?TRIGGER_LOW_SET?')
            if adc_trig_low != -1:
                response = str(trigger_low_set)
                done_parse = 1
            
            # Look for request to get trigger limits
            adc_trig_high = request.find('?TRIGGER_HIGH_SET?')
            if adc_trig_high != -1:
                response = str(trigger_high_set)
                done_parse = 1
            
            # Look for ?FAN_SET=
            low_set = request.find('?TRIGGER_LOW_SET=')
            if low_set != -1:
                low_set_done = request.find('TRIGGER_LOW_SET?')
                
                if low_set_done != -1:
                    try:
                        # Get the integer from the string
                        trigger_low_set = int(request[(low_set + 17) : low_set_done])                    
                        
                        # Send the value back to the user
                        response = str(trigger_low_set)
                        
                        done_parse = 1
                    
                    except OSError as error:
                        # Bad setting
                        print(error)
                                                
                        response = "0"
                        done_parse = 1
                        
            # Look for ?FAN_SET=
            high_set = request.find('?TRIGGER_HIGH_SET=')
            if high_set != -1:
                high_set_done = request.find('TRIGGER_HIGH_SET?')
                
                if high_set_done != -1:
                    try:
                        # Get the integer from the string
                        trigger_high_set = int(request[(high_set + 18) : high_set_done])                    
                        
                        # Send the value back to the user
                        response = str(trigger_high_set)
                        
                        done_parse = 1
                    
                    except OSError as error:
                        # Bad setting
                        print(error)
                                                
                        response = "0"
                        done_parse = 1
                    
            # ADC values?
            adc_pre_val = request.find('?ADC_PRE_VAL?')
            if adc_pre_val != -1:
                # Re-order the output so it is correct in time...
                temp_samp = (pre_sample + 1) % N_pre_trigger
                # Start the string
                response = str(adc_array_pretrigger[temp_samp])
                # Add the rest
                for ii in range(1, N_pre_trigger):
                    temp_samp = (temp_samp + 1) % N_pre_trigger
                    response = response + ", " + str(adc_array_pretrigger[temp_samp])
                
                # Add the main array too
                for ii in range(N_array):
                    response = response + ", " + str(adc_array[ii])
                
                done_parse = 1
            
            # Look for request to kick off ADC capture
            adc_cap = request.find('?GO_ADC?')
            if adc_cap != -1:
                # Kick off the ADC capture
                capture_state = 1
                response = "ok"
                done_parse = 1
                            
            # ADC values?
            adc_val = request.find('?ADC_VAL?')
            if adc_val != -1:
                response = str(adc_array[0])
                
                for ii in range(1, N_array):
                    response = response + ", " + str(adc_array[ii])
                    
                done_parse = 1
            
            # Assume the outside user wants a file
            # Look for the "GET" text
            base_file = request.find('GET /')            
            if (base_file == 2) & (done_parse == 0):
                # Look for the "HTTP" text
                end_name = request.find(' HTTP')
                
                if end_name != -1:
                    # Get the filename
                    f_name = request[7 : end_name]
                    
                    # Print the filename
                    print("filename: " + f_name)
                    
                    found_file = 0
                    try:                    
                        # Get the file size, in bytes
                        temp = os.stat(f_name)
                        found_file = 1
                        
                    except OSError as error:
                        # Likely the file was not found
                        print(error)
                        print("Likely, bad filename...")
                                                
                    if found_file == 1:
                        try:
                            f_size_bytes = temp[6]
                            fid = open(f_name, 'rb')
                            response = fid.read()
                            print(len(response))
                            fid.close()
                        except OSError as error:
                            print(error)
                            print("Likely, file too big to open and send...")
            
            # Send the response
            cl.send('HTTP/1.0 200 OK\r\nContent-Length: ' + str(len(response)) + '\r\nConnection: Keep-Alive\r\n\r\n')
            cl.sendall(response)                        
            cl.close()
            
        except OSError as e:
            print(e)
            cl.close()
            print('connection closed')
