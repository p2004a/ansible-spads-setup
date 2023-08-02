# Ansible Installation

## On each client (SPADS server)
Install python3.
> sudo apt install python3

## On the Ansible server
1. Install Ansible and sshpass.
   > sudo apt install ansible sshpass
2. SSH to each client once and accept their key to add them to the known hosts.
3. Checkout this repo and then run any following Ansible command from the checked out folder.
4. Modify the inventory file (use **ansible-vault edit inventory**) to have all the SPADS servers and also group them under [spads]
5. Configure the variable files (use **ansible-vault edit (filename)**):
   - groups_vars/all.yaml - contains the variables that will be applied to every spads server
   - groups_vars/(region).yaml - contains the variables specific to a region (AU, EU, US). Anything set here will override groups_vars/all.yaml
   - host_vars/(hostname).yaml - contains the variables specific to the host. Anything set here will override groups_vars/all.yaml and groups_vars/(region).yaml
6. Run Ansible. The typical syntax for running Ansible with some files encrypted with Ansible Vault is:
   > ansible-playbook (playbookfile) -i (inventoryfile) --ask-vault-pass

   If no files are encrypted --ask-vault-pass can be removed.

   Run can be limited to a specific host with --limit (hostname) \
   Note: use the hostname set in the inventory file
   > ansible-playbook (playbookfile) -i (inventoryfile) --limit (hostname)

# Examples

**Configure/verify SPADS is configured properly on all servers**
> ansible-playbook play.yaml -i inventory --ask-vault-pass

**Restart all SPADS services only on US2**
> ansible-playbook restart.yaml -i inventory --limit us2 --ask-vault-pass

**Run Ansible with no encrpyted files**
> ansible-playbook play.yaml -i inventory

# Available playbooks:
- play.yaml - configure SPADS/verify SPADS is configured properly
- delete.yaml - delete SPADS files and services
- restart.yaml - restart all SPADS services
- start.yaml - start all SPADS services
- stop.yaml - stop all SPADS services
- engineupdate.yaml - runs spads_config_bar_updater.py -c -u (doesn't restart SPADS)

# Ansible Vault
Ansible Vault provides a way to encrypt sensitive information used by Ansible. It'll prompt for the password when running a command.

**View encrypted file**
> ansible-vault view file1.yaml file2.yaml file3.yaml

**Encrypt an existing file**
> ansible-vault encrypt file1.yaml file2.yaml file3.yaml

**Edit an encrypted file**
> ansible-vault edit file.yaml

**Decrypt a file**
> ansible-vault decrypt file1.yaml file2.yaml file3.yaml

**Change the encrpytion key of a file**
> ansible-vault rekey file1.yaml file2.yaml file3.yaml

# Local testing

It might be useful to test the playbook fully locally, and it's possible to do
so in containers. Below we use podman rootless containers, but it should be
analogous using docker.

1. Build base image 

   ```
   podman build --build-arg=SSH_PUB_KEY="$(ssh-add -L | head -n 1)" \
   -f testsrv.Dockerfile -t spads-testsrv
   ```

1. Start the container

   ```
   podman run --publish-all --detach --name spads spads-testsrv
   ```

   It can be later started/sroped/removed with standard podman commands.

1. Run playbook against the system running in container

   ```
   ansible-playbook play.yaml -i localhost, \
      --skip-tags container_incompatible \
      -e ansible_ssh_port=$(podman port spads 22 | cut -d: -f2) \
      -e ansible_user=root --ask-vault-pass
   ```

1. Connect to container

   ```
   ssh root@localhost -p $(podman port spads 22 | cut -d: -f2)
   ```
