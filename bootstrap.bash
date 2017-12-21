#!/bin/bash

set -e

# install and run ansible
{
	export DEBIAN_PRIORITY=high DEBIAN_FRONTEND=noninteractive
	add-apt-repository -y ppa:ansible/ansible
	apt-get update
	apt-get -y install ansible
} > /dev/null
(
	cd data100
	sudo -u jupyterhub -H ansible-playbook playbook.yml
)
