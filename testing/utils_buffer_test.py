"""
Test the line buffering to improve speed of files
"""

import io
import unittest

from rdiffbackup.utils import buffer


class UtilsBufferTest(unittest.TestCase):
    """
    Test the buffer module
    """

    def test_buffer_read_write(self):
        """Test writing and reading back lines using buffer"""
        write_io = io.BytesIO()
        write_lines = buffer.LinesBuffer(write_io, b"|")
        for line in range(0, 65535):
            write_lines.write(str(line).encode())
        write_lines.flush()
        read_io = io.StringIO(write_io.getvalue().decode())
        read_lines = buffer.LinesBuffer(read_io, "|")
        for x, y in zip(read_lines, range(0, 65535), strict=True):
            self.assertEqual(int(x), y)


if __name__ == "__main__":
    unittest.main()
