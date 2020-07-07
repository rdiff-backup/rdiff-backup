# Vagrant setup for testing older versions of rdiff-backup

Just call `vagrant up` to get the version.

If you want to get a different version of rdiff-backup than the default one in
`host_vars`, use following command:

```
ansible-playbook playbook-provision.yml -e rdiff_backup_old_version=2.0.3
```

To come back to the default version, just leave out the `-e xxx` option
(or simply call `vagrant provision`).

You may call the smoke tests using the following command and validate that
nothing wrong happens:

```
ansible-playbook -v playbook-smoke-test.yml
```

You can use the current development version by using something like the following,
after having built from source using `./setup.py build`:

```
PATH=../../build/scripts-3.8:$PATH PYTHONPATH=../../build/lib.linux-x86_64-3.8 \
	ansible-playbook -v playbook-smoke-test.yml
```

> **CAUTION:** the version shown locally might be DEV or any other version
	installed elsewhere locally, but the version used is definitely the
	built development version.
