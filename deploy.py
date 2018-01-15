#!/usr/bin/env python3

import argparse
import json
import os
import subprocess as sp
import sys
import yaml

def write_json(filename, data):
	f = open(filename, 'w')
	f.write(json.dumps(data, indent=4, separators=(',', ': ')))
	f.close()

parser = argparse.ArgumentParser(description='Deploy JupyterHub on Kubernetes on Azure')
parser.add_argument('-s', dest='subscription_id', required=True,
	help='Azure subscription id.')
parser.add_argument('-n', dest='name', required=True,
	help='Cluster name.')
parser.add_argument('-r', dest='rbac', default='rbac.json',
    help='Service principal file, relative to output dir. Will be created if it does not exist. [default=rbac.json].')
parser.add_argument('-d', dest='disks', type=int, default=4,
	help='Managed disk count [default=4].')
parser.add_argument('-D', dest='disk_size', type=int, default=1024,
	help='Disk size (gb) [default=1024].')
parser.add_argument('-l', dest='location', default="centralus",
	help='Azure Region [default=westus].')
args = parser.parse_args()

# stash output data
if not os.path.exists(args.name):
	os.mkdir(args.name)
elif not os.path.isdir(args.name):
	print(args.name + " exists and is not a directory.")
	sys.exit(1)

# create an ssh keypair
ssh_key = os.path.join(args.name, 'id_rsa')
ssh_key_pub = ssh_key + '.pub'
if not os.path.exists(ssh_key):
	cmd = ['ssh-keygen', '-t', 'rsa', '-N', '', '-f', ssh_key]
	r = sp.check_output(cmd)
ssh_key_data = open(ssh_key_pub).read()

# make sure we're using our subscription
cmd = ['az', 'account', 'set', '-s', args.subscription_id]
r = sp.check_output(cmd)

# prepare az service principals
rbac_file = os.path.join(args.name, args.rbac)
if not os.path.exists(rbac_file):
	cmd = ['az', 'ad', 'sp', 'create-for-rbac',
		'--scopes=/subscriptions/{}'.format(args.subscription_id),
		'--role=Contributor']
	rbac_s = sp.check_output(cmd, universal_newlines=True)
	f = open(rbac_file, 'w')
	f.write(rbac_s)
	f.close()
else:
	rbac_s = open(rbac_file).read()
rbac = json.loads(rbac_s)

# check our groups
cmd = ['az', 'group', 'list', '--query', "[?name=='{}']".format(args.name)]
r = sp.check_output(cmd)
groups = json.loads(r.decode())
if len(groups) == 0:
	print("Creating group: {}".format(args.name))
	cmd = ['az', 'group', 'create', '-n', args.name, '-l', args.location]
	r = sp.check_output(cmd)
else:
	print("Using existing group: {}".format(args.name))

# create hub server
vm_name = 'hub'
cmd = [
	'az', 'vm', 'create',
		'-n', vm_name,
		'--admin-username', 'jupyterhub',
		'--resource-group', args.name,
		'--ssh-key-value', ssh_key_pub,
		'--size', 'Standard_E4s_v3',
		'--storage-sku', 'Premium_LRS',
		'--image', 'canonical:ubuntuserver:17.04:latest'
]
vm_create = sp.check_output(cmd, universal_newlines=True)
write_json(os.path.join(args.name, vm_name + '.json'), vm_create)

# create and attach disks
for i in range(1, args.disks + 1):
	r = sp.check_output(['az', 'vm', 'disk', 'attach', '--new',
		'--disk', vm_name + '-' + str(i),
		'--resource-group', args.name,
		'--vm-name', vm_name,
		'--size-gb', str(args.disk_size),
		'--sku', 'Premium_LRS']) 

# run install script
cmd = ['az', 'vm', 'extension', 'set',
	'--resource-group', args.name,
	'--vm-name', vm_name,
	'--name', 'customScript',
	'--publisher', 'Microsoft.Azure.Extensions',
	'--settings', './script-config.json']
r = sp.check_output(cmd, universal_newlines=True)

# prepare to connect to master
ssh_opts = [
	'-i', ssh_key,
	'-o', 'UserKnownHostsFile=/dev/null',
	'-o', 'StrictHostKeyChecking=no',
	'-o', 'PreferredAuthentications=publickey',
	'-o', 'User=jupyterhub'
]
ssh_host = '{}.{}.cloudapp.azure.com'.format(args.name, args.location)
os.environ['SSH_AUTH_SOCK'] = ''

# verify ssh works
cmd = ['ssh'] + ssh_opts + [ssh_host, 'true']
try:
	sp.check_call(cmd)
except Exception as e:
	print("Error running command:")
	print(" ".join(cmd))
	print(str(e))

# copy ansible playbook
cmd = ['ssh'] + ssh_opts + [ssh_host, "git clone https://github.com/ryanlovett/data100.git"]
sp.check_call(cmd)

# run bootstrap
cmd = ['ssh'] + ssh_opts + [ssh_host, "sudo bash data100/bootstrap.bash " + args.name]
sp.check_call(cmd)
