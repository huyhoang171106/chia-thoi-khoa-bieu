"""Parsing and writing for the SQL Server migration, using canned SQL Server output."""
import base64
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import migrate_sqlserver as migrate  # noqa: E402


class MigrateTest(unittest.TestCase):
    def test_round_trip(self):
        salt, passhash = '0' * 32, 'a' * 64
        users = migrate.parse_users(f'1|teacher1|{salt}|{passhash};2|co.lan|{salt}|{passhash};')
        self.assertEqual([u[:2] for u in users], [(1, 'teacher1'), (2, 'co.lan')])
        state = '{"term":"Học kỳ I","teachers":[{"name":"Cô Lan 👩‍🏫"}]}'
        encoded = base64.b64encode(state.encode('utf-16-le')).decode()
        self.assertEqual(migrate.decode(encoded[:40] + '\r\n' + encoded[40:]), state)
        self.assertIsNone(migrate.decode(''))
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'db.sqlite'
            self.assertFalse(migrate.has_users(target))
            migrate.write(target, users, [(1, state)], '{"term":"legacy"}')
            self.assertTrue(migrate.has_users(target))
            with sqlite3.connect(target) as db:
                self.assertEqual(db.execute('SELECT data FROM user_state WHERE user_id = 1').fetchone()[0], state)
                self.assertEqual(db.execute('SELECT count(*) FROM users').fetchone()[0], 2)

    def test_rejects_bad_rows(self):
        with self.assertRaises(SystemExit):
            migrate.parse_users("1|Robert'); DROP TABLE x;--|" + '0' * 32 + '|' + 'a' * 64 + ';')


if __name__ == '__main__':
    unittest.main()
