"""
Test the API functions
"""

import os
import subprocess
import unittest
import yaml

import commontest as comtst

from rdiff_backup import Globals
from rdiffbackup import actions

TEST_BASE_DIR = comtst.get_test_base_dir(__file__)


class ApiVersionTest(unittest.TestCase):
    """Test api versioning functionality"""

    def test_runtime_info_calling(self):
        """make sure that the info output can be read back as YAML"""
        latest_api = Globals.api_version["max"]
        output = subprocess.check_output(
            [comtst.RBBin, b"--api-version", b"%i" % latest_api, b"info"]
        )
        out_info = yaml.safe_load(output)
        self.assertEqual(out_info["exec"]["parsed"]["action"], "info")

        Globals.api_version["actual"] = latest_api
        # we make sure that the parsed info is the same
        info = actions.BaseAction.get_runtime_info(parsed=out_info["exec"]["parsed"])

        # because the current test will have a different call than rdiff-backup
        # itself, we can't compare certain keys
        self.assertIn("exec", out_info)
        self.assertIn("argv", out_info["exec"])
        out_info["exec"].pop("argv")
        info["exec"].pop("argv")

        # info['python'] could also be different, under special conditions
        self.assertIn("python", out_info)
        self.assertIn("executable", out_info["python"])
        out_info.pop("python")
        info.pop("python")

        self.assertEqual(info, out_info)

    def test_default_actual_api(self):
        """validate that the default version is the actual one or the one explicitly set"""
        output = subprocess.check_output([comtst.RBBin, b"info"])
        api_version = yaml.safe_load(output)["exec"]["api_version"]
        self.assertEqual(Globals.get_api_version(), api_version["default"])
        api_param = os.fsencode(str(api_version["max"]))
        output = subprocess.check_output(
            [comtst.RBBin, b"--api-version", api_param, b"info"]
        )
        out_info = yaml.safe_load(output)
        self.assertEqual(out_info["exec"]["api_version"]["actual"], api_version["max"])

    def test_debug_output(self):
        """Use verbosity 9 to cover debug functions in logging"""
        output = subprocess.check_output(
            [comtst.RBBin, b"-v", b"9", b"--terminal-verbosity", b"9", b"info"]
        )
        self.assertIn(b"DEBUG: Runtime information =>", output)

    def test_env_var(self):
        """Test usage of the environment variable"""
        # Python under Windows needs the variable SYSTEMROOT
        # or it fails with a randomization init error, hence we copy the
        # environment and extend it instead of creating a new one.
        local_env = os.environ.copy()
        local_env["RDIFF_BACKUP_API_VERSION"] = "{min: 111, max: 999}"
        output = subprocess.check_output([comtst.RBBin, b"info"], env=local_env)
        api_version = yaml.safe_load(output)["exec"]["api_version"]
        self.assertEqual(api_version["min"], 111)
        self.assertEqual(api_version["max"], 999)
        # make sure the untouched variables are really untouched
        self.assertEqual(Globals.get_api_version(), api_version["default"])


if __name__ == "__main__":
    unittest.main()
