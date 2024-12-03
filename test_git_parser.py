import unittest
import os
import toml
import zlib
import re
from unittest.mock import patch, mock_open

from main import (
    load_config,
    parse_object,
    parse_commit,
    get_last_commit
)


class TestGitParser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Путь к hw2_dir относительно текущего файла
        cls.project_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        cls.repo_path = os.path.join(cls.project_dir, 'hw2_dir')
        cls.git_dir = os.path.join(cls.repo_path, '.git')  # Убедимся, что .git в правильном месте

        cls.config_data = {
            'repo_path': cls.repo_path,
            'branch': 'master'  # Проверяйте на корректность ветку
        }
        cls.config_toml = toml.dumps(cls.config_data)

        cls.fake_git_object = {
            "commit": b"commit 150\x00tree 4b825dc642cb6eb9a060e54bf8d69288fbee4904\n",
            "tree": b"100644 example.txt\x00abcd1234ef567890abcd1234ef567890abcd1234",
            "blob": b"blob 1000\x00Hello, World!"
        }

    @patch('builtins.open', new_callable=mock_open, read_data="master_branch_commit_hash\n")
    def test_get_last_commit(self, mock_file):
        with patch.dict('os.environ', {'repo_path': self.repo_path}):
            commit_hash = get_last_commit()
            mock_file.assert_called_once_with(
                os.path.join(self.repo_path, '.git', 'refs', 'heads', 'master'), 'r'
            )
            self.assertEqual(commit_hash, "master_branch_commit_hash")

    @patch("main.open", new_callable=mock_open)
    @patch("main.parse_commit")
    @patch("main.parse_object")
    def test_parse_object_commit(self, mock_parse_object, mock_parse_commit, mock_open):
        # Подготовим тестовое содержимое и сожмем его
        test_data = b"commit 150\x00tree 4b825dc642cb6eb9a060e54bf8d69288fbee4904\n"
        compressed_data = zlib.compress(test_data)

        # Подготовим поведение mock
        mock_open.return_value.read.return_value = compressed_data
        # Поменяем поведение mock_parse_object
        mock_parse_object.side_effect = lambda hash: {"label": "commit", "children": []} if hash.startswith(
            "4b") else {}
        # Изменим mock_parse_commit, чтобы оно возвращало пустой список для коммита
        mock_parse_commit.side_effect = lambda data: []  # Возвращаем пустой список для коммита

        commit_hash = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
        result = parse_object(commit_hash)

        # Убираем лишние символы, используя регулярное выражение
        cleaned_result_label = re.sub(r"\[commit\].*", "commit", result["label"]).strip()

        # Проверяем, что вернулась метка 'commit'
        self.assertEqual(cleaned_result_label, "commit")
        self.assertEqual(result["children"], [])  # Проверяем, что дети пусты
        mock_open.assert_called_once_with(
            '/Users/juliavediukova/STUDY/конфигурационное управление/hw2_dir/.git/objects/4b/825dc642cb6eb9a060e54bf8d69288fbee4904',
            'rb')

    def test_parse_commit(self):
        raw_commit_data = b"tree abcd1234\nparent def5678\n\nTest message"
        with patch("main.parse_object", return_value={"label": "[tree]", "children": []}):
            result = parse_commit(raw_commit_data)
            self.assertEqual(result[0]["label"], "[tree]")

    @patch('os.path.join')
    def test_invalid_path(self, mock_join):
        mock_join.return_value = "/invalid/path"
        with self.assertRaises(FileNotFoundError):
            parse_object("invalid_hash")


if __name__ == "__main__":
    unittest.main()