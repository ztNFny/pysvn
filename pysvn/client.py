from datetime import datetime
import subprocess
from subprocess import Popen
import os
from typing import List, Union
import xml.etree.ElementTree
import pathlib

from errors import RepositoryDirDoesNotExistError, SVNNotInstalledError, NoSuchRevisionError, RevisionSyntaxError

from models import LogEntry, Revision, Diff, SVNItemPath

from utils import check_svn_installed

class Client:
    def __init__(self, repository_dir: str = os.getcwd()) -> None:
        if not check_svn_installed():
            raise SVNNotInstalledError('Is svn installed? If so, check that its in path.')

        repo_dir = pathlib.Path(repository_dir)
        if not repo_dir.exists():
            raise RepositoryDirDoesNotExistError('the repository_dir provided does not exist')
        if not repo_dir.is_dir():
            raise NotADirectoryError('the repository_dir provided is not a directory')

        self.cwd = str(repo_dir.resolve())
        

    def log(self, file: str = None, revision: Union[int, Revision, str] = Revision.HEAD) -> List[LogEntry]:
        revision = revision.name if type(revision) == Revision else revision
        log_cmd = f'log --xml --revision {revision}' if not file else f'log {file} --xml --revision {revision}'
        log_entries: List[LogEntry] = []
        cmd = self._run_svn_cmd(log_cmd.split(' '))

        stderr = cmd.stderr.read()
        if stderr and 'No such revision' in stderr.decode('utf-8'):
            rev_num = stderr.decode('utf-8').split(' ')[-1]
            raise NoSuchRevisionError(f'no such revision {rev_num}')

        data = cmd.stdout.read()
        
        try:
            root = xml.etree.ElementTree.fromstring(data)

            for e in root.iter('logentry'):
                entry_info = {x.tag: x.text for x in list(e)}

                date = None
                if entry_info.get('date'):
                    date_str = entry_info.get('date').split('.', 1)[0]
                    date = datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%S')

                log_entry = LogEntry(
                    message=entry_info.get('msg'),
                    author=entry_info.get('author'),
                    revision=int(e.get('revision')),
                    date=date
                )

                log_entries.append(log_entry)

            return log_entries
        except xml.etree.ElementTree.ParseError:
            raise RevisionSyntaxError(f"with great power comes great responsibility, '{revision}' is not valid revision syntax")


    def _run_svn_cmd(self, args: List[str]) -> Popen[bytes]:
        args.insert(0, 'svn')
        return subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=self.cwd)


    def __svn_update__(self) -> None:
        self._run_svn_cmd(['update'])


    def diff(self, start_revision: int, end_revision: int = None) -> Diff:
        self.__svn_update__()

        if not end_revision:
            end_revision = 'HEAD'

        cmd = self._run_svn_cmd(['diff', '-r', f'{start_revision}:{end_revision}', '--xml', '--summarize'])
        
        stderr = cmd.stderr.read()
        if stderr and 'No such revision' in stderr.decode('utf-8'):
            rev_num = stderr.decode('utf-8').split(' ')[-1]
            raise NoSuchRevisionError(f'no such revision {rev_num}')

        data = cmd.stdout.read()
        paths: List[SVNItemPath] = []
        root = xml.etree.ElementTree.fromstring(data)
        
        for e in root.iter('path'):
            attrs = e.attrib
            filepath = e.text
            svn_path = SVNItemPath(
                item=attrs.get('item'),
                props=attrs.get('props'),
                kind=attrs.get('kind'),
                filepath=filepath
            )
            paths.append(svn_path)

        return Diff(paths)


def main() -> None:
    svn = Client(repository_dir='../tests/test_svn')
    print(svn.diff(1))

if __name__ == '__main__':
    main()
