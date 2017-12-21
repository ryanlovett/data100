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
	cd k8s-nfs-ansible
	sudo -u jupyterhub -H ansible-playbook -i hosts playbook.yml
)
