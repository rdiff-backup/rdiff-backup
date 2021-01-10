# Windows development environment

## Create the Windows VM

Install Vagrant, ruby-devel and libvirt-devel as root and the necessary
plug-ins with `vagrant plugin install <plugin>`:

- vagrant-libvirt (_not_ libvirt!)
- winrm
- winrm-elevated

A simple `vagrant up` should now do, using a default Windows image, and you'll
get in the best case a fully workable rdiff-backup development environment on
Windows.

> **NOTE:** Starting from https://github.com/redhat-cop/automate-windows/tree/master/vagrant-libvirt-image,
>	you can create your own Windows VM usable by Ansible (any other alternative
>	approach to a such VM is of course valid).

You can re-apply the changes using `vagrant provision` or direcly apply the
playbook `playbook-provision-windows.yml` using Ansible to the Windows you've
just created to create the necessary development environment.

> **IMPORTANT:** The current state of the automation isn't very satisfying, the more complex packages need to be installed manually from the command line with something like `choco install <packagename>` and the playbook restarted. A few reboots in-between might be necessary.

If you already have a Windows VM/PC/laptop/server, you'd like to use for
rdiff-backup development, you don't need to use Vagrant, you can directly
use Ansible:

1. Make your [Windows host ready for Ansible](https://docs.ansible.com/ansible/latest/user_guide/windows_setup.html).
2. Create an inventory that looks as after this list.
3. Call directly the provisioning playbook
   `ansible-playbook -i YOURINVENTORYFILE playbook-provision-windows.yml`.

Your inventory should look as follows, depending on your exact Windows setup,
replacing at least the `MY*` placeholders (some level of Ansible knowledge
doesn't hurt here):

```
[windows_ansible]
MYWINDOWSHOST ansible_host=192.168.1.MYIP ansible_user='MYUSER' ansible_password='MYPASSWORD'

[windows_ansible:vars]
ansible_connection=winrm
ansible_port=5986
ansible_winrm_server_cert_validation=ignore
```

> **TIP:** with the newest version of Windows, you can even connect to the VM using SSH e.g. with `vagrant ssh`.

## Build librsync and rdiff-backup

It can be as easy as calling twice ansible-playbook:

```
ansible-playbook playbook-build-librsync.yml
ansible-playbook playbook-build-rdiff-backup.yml
```

> **NOTE:** you can use the variables under `group_vars/all` to steer the build process, check the comments there for more details.

## Develop and try under Windows

Open a console and type:

```
cd %HOME%\Develop\rdiff-backup
.\build\setup-rdiff-backup.bat
.\build\scripts-3.9\rdiff-backup --version
.\build\scripts-3.9\rdiff-backup sourcedir targetdir
python -m pdb .\build\scripts-3.9\rdiff-backup sourcedir targetdir
[...]
```

If you do changes to the source code, just rebuild using one or both playbooks and try again.

> **NOTE**: If you do changes outside of the VM, you'll need to do `git pull` on your own, the playbooks doesn't (yet) take care of it for you.

## Samba server

If you need a samba server to do some specific tests, you can simply call
explicitly `vagrant up samba`, followed by something like `vagrant ssh samba`
to log onto the machine.

There are 2 shares available, one `\\samba\readonlyshare` and one `\\samba\readwriteshare`,
(the difference should be obvious), which you can map on the Windows VM using
a command like `net use x: \\samba\whichevershare` (or use directly).

## Miscellaneous considerations

### Vagrant and Ansible

Vagrant manages an inventory file for Ansible, so that commands like the following ones are possible:

```
ansible -i .vagrant/provisioners/ansible/inventory/vagrant_ansible_inventory -m win_reboot default
ansible-playbook -i .vagrant/provisioners/ansible/inventory/vagrant_ansible_inventory playbook-provision-windows.yml -vvvvv
```

### Libvirt

After the installation of the virtio drivers, shutdown the VM and go to the virtmanager and change following parameters to get more performance:

* OS information -> Operating System -> Microsoft Windows 10

Those two settings were overwritten at next `vagrant up` and led to some issues:

* Video _whatever_ -> Model: Virtio, 3D acceleration: set
* Display VNC -> Type: Spice server, Listen type: none and OpenGL: set

Those two settings didn't work as expected and made boot resp. network fail:

* SATA Disk 1 -> Advanced options -> Disk bus: VirtIO
* NIC _whatever_ -> Device model: virtio

### Chocolatey

The logs of Chocolatey are available under `C:\ProgramData\chocolatey\logs` and `C:\Users\IEUser\AppData\Local\Temp\chcolatey`.

At some point in time, the VS Code packaging for the VC workload was broken and
the only solution was to call _as administrator_ from the command line in the
Windows VM
`C:\Program Files (x86)\Microsoft Visual Studio\Installer\vs_installer.exe" modify --installPath "C:\Program Files (x86)\Microsoft Visual Studio\2017\BuildTools" --includeRecommended --norestart --quiet --add Microsoft.VisualStudio.Workload.VCTools`.

### Cygwin

You can install new Cygwin packages using `cyg-get.bat`, e.g. `cyg-get vim` or `cyg-get /?` (`cyg-get --help` isn't foreseen but seems to give much more parameters).

You can start Cygwin using `\tools\cygwin\Cygwin.bat`.

