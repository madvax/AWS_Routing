#!/usr/bin/env python

# This script allows the user to alter the routing of the DNS Failover in AWS.
# the DNS Failover is configured to route http://www.cos3.rocks/index.html
# to an AWS EC2 instance in US-East-2 (Ohio) via a TCP Elastic Load Blanacer.
# If the server in Ohio is down then the DNS will 'failover' to an AWS EC2 
# instance in EU (Frankfurt). This script will detect which of the servers 
# is currently being resolved when www.cos3.rocks is queried then, change the 
# routing.

# =============================================================================
# STANDARD LIBRARY IMPORTS
import sys
import os
import urllib2
import time
from getopt import getopt
import subprocess

# =============================================================================
# THIRD PARTY LIRARY IMPORTS
try:
   import boto3
   from botocore.exceptions import ClientError
except:
   sys.stderr.write("ERROR -- Unable to import the boto3 site package.\n")
   sys.stderr.write("         try: pip install boto3 \n\n")
   sys.exit(1)

# =============================================================================
# DICTIONARY OF VARIABLES
VERSION        = "1.2.0"   # Version for this library
DEBUG          = False     # Flag for debug operation
VERBOSE        = False     # Flag for verbose operation
FIRST          = 0         # First list index
LAST           = -1        #  Last list index
ME             = os.path.split(sys.argv[FIRST])[LAST]        # Name of this file
MY_PATH        = os.path.dirname(os.path.realpath(__file__)) # Path for this file
INSTANCE_ID    = 'i-034f6c3491e1661a4'
STATES         = ['pending', 'running', 'stopping', 'stopped']
ec2            = boto3.client('ec2')
TARGET_URL     = "http://www.cos3.rocks/index.html"
AUTO_OPERATION = True
PEM_FILE       = "qa-cos3.pem"
WEB_SERVER_CMD = "/usr/bin/sudo ./webserver.py -i 172.31.28.197  >/dev/null 2>&1 &"

# =============================================================================
# NATIVE CLASSES
class Command:
   """ Command() --> Command Object """
   #--------------------------------------------------------- Command.__init__()
   def __init__(self, command):
      """ Creates an instance of an object of type Command. """
      self.command    = str(command).strip()   # The command to execute
      self._stdout    = subprocess.PIPE        # Standard Output PIPE
      self._stderr    = subprocess.PIPE        # Standard Error PIPE
      self.output     = "Command not executed" # Output from command
      self.error      = "Command not executed" # Error from command
      self.returnCode = 127                    # Default return code from command

   # ------------------------------------------------------------- Command.run()
   def run(self):
      """ Executes the command  """
      try:
         results = subprocess.Popen(self.command          ,
                                    stdout = self._stdout ,
                                    stderr = self._stderr ,
                                    shell  = True         ) # Execute the command
         self.output, self.error = results.communicate() # Get output and error
         self.returnCode         = results.returncode    # Get Return Code
      except Exception, e:
         self.output      = str(e)
         self.error       = "Unable to execute: \"%s\"" %self.command
         self.returnCode  = 113

   # ----------------------------------------------------- Command.showResults()
   def showResults(self):
      """ Prints original command and resutls to stdout. """
      print "COMMAND     : \"%s\"" %self.command
      print "OUTPUT      : \"%s\"" %self.output.strip()
      print "ERROR       : \"%s\"" %self.error.strip()
      print "RETURN CODE : %d"     %self.returnCode

   # ---------------------------------------------------- Command.returnResuls()
   def returnResults(self):
      """ Returns a dictionary containing the original command  and results. """
      results = {"command"    : self.command.strip() ,
                 "output"     : self.output.strip()  ,
                 "error"      : self.error.strip()   ,
                 "returnCode" : self.returnCode      }
      return results

# =============================================================================
# NATIVE FUNCTIONS
def usage():
   """usage() - Prints the usage message on stdout. """
   print "\n\n%s, Version %s, Time Delay Web Server."  %(ME,VERSION)
   print ""
   print "This script allow the user to alter the routing of the DNS Failover in AWS."
   print "the DNS Failover is configured to route http://www.cos3.rocks/index.html"
   print "to an AWS EC2 insgtance in US-East-2 (Ohio) via a TCP Elastic Load Blanacer."
   print "If the server in Ohio is down then the DNS will 'failover' to an AWS EC2"
   print "instance in EU (Frankfurt). This script will detect which of the servers"
   print "is currently being resolved when www.cos3.rocks is queried then, toggle the"
   print "the routing."
   print ""
   print "\nUSAGE: %s [OPTIONS]                                    " %ME
   print "                                                         "
   print "OPTIONS:                                                 "
   print "   -h --help       Display this message.                 "
   print "   -v --verbose    Runs the program in verbose mode, default: %s.        " %VERBOSE
   print "   -d --debug      Runs the program in debug mode (implies verbose)      "
   print ""
   print "EXIT CODES:                                              "
   print "   0 - Clean Exit"
   print "   1 - The boto3 site package not installed on the system"
   print "   2 - Bad or missing command line argument"
   print "   3 - Unable to determine initial server state"
   print " Other Non-Zero - Failure of some sort or another"
   print "                                                         "
   print "EXAMPLES:                                                "
   print "    TODO - I'll make some examples up later.             "
   print "                                                         "

# =============================================================================
# MAIN 

# -----------------------------------------------------------------------------
# Step 1: Parse the comamnd line arguments
try:
   arguments = getopt(sys.argv[1:] ,
                      'hvd'        ,
                      ['help'    ,
                       'verbose' ,
                       'debug'   ] )
except:
   sys.stderr.write("ERROR -- Bad or missing command line argument(s)\n\n")
   usage()
   sys.exit(2)
# --- Check for a help option
for arg in arguments[0]:
   if arg[0] == "-h" or arg[0] == "--help":
     usage()
     sys.exit(0)
# --- Check for a verbose option
for arg in arguments[0]:
   if arg[0]== "-v" or arg[0] == "--verbose":
      VERBOSE = True
# --- Check for a debug option
for arg in arguments[0]:
   if arg[0]== "-d" or arg[0] == "--debug":
      DEBUG   = True
      VERBOSE = True

# -----------------------------------------------------------------------------
# Step 2: verify the pem file for access to the ec2 instance 
ssh_folder = os.path.join(os.environ['HOME'], ".ssh")
public_key = os.path.join(ssh_folder, PEM_FILE)
if DEBUG: print "Using %s for authentication " %public_key
if not os.path.exists(public_key):
   sys.stderr.write("ERROR -- Unable to verify the PEM file \"%s\"\n" % PEM_FILE)
   sys.stderr.write("         Please ensure the file exists.")
   sys.exit(4)

# -----------------------------------------------------------------------------
# Step 3: Determine if the server is up
if DEBUG: print "Checking instance ID: %s" %INSTANCE_ID
try:
   status =  ec2.describe_instances(InstanceIds=[INSTANCE_ID])['Reservations'][FIRST]['Instances'][FIRST]['State']['Name']
   if DEBUG: print "Server State: %s" %status
   if status == "running":
      server_is_up = True
   else:
      server_is_up = False
except Exception as e:
   sys.stderr.write("ERROR -- Unable to determine the state of the server.\n")
   sys.stderr.write("         Check network connectivity and account permissions.\n")
   sys.exit(3)

# -----------------------------------------------------------------------------
# Step 4: Make the necessary routing chagnes
if AUTO_OPERATION:
   if server_is_up:
      if VERBOSE: print "Stopping US-East-2 (Ohio) EC2 instance"
      ec2.stop_instances(InstanceIds=[INSTANCE_ID])
      if VERBOSE: print "Done. It may take a few minutes to observe the route change."
   else:
      if VERBOSE: print "Starting US-East-2 (Ohio) instances"
      ec2.start_instances(InstanceIds=[INSTANCE_ID])
      if VERBOSE: print "After the server starts the http damon will need to be started."
      if VERBOSE: print "Please wait a few minutes for all of this to get going ..."
      time.sleep(150)
      ssh_params = "-o UserKnownHostsFile=/dev/null -o CheckHostIP=no -o StrictHostKeyChecking=no "
      cmd = "/usr/bin/ssh %s -i %s %s@%s \"%s\"" %(ssh_params      ,
                                                   public_key      ,
                                                   "ubuntu"        ,
                                                   "18.221.85.157" ,
                                                   WEB_SERVER_CMD  ) # Its ok to hard code. Its an Elastic ip
      c = Command(cmd)
      c.run()
      if VERBOSE: c.showResults()

sys.exit(0)
