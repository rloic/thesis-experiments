#!/usr/bin/python3
import datetime
import getpass
import os
import shutil
import subprocess
from urllib.parse import quote
from typing import Dict, List, Union, TypeVar

import yaml
import sys

T = TypeVar('T')


def safe_run(cmd: str) -> bool:
    status = subprocess.call(cmd.split(' '))
    if status != 0:
        print(' | Fail to run cmd: {}', cmd)
    return status == 0


class Requirement:
    def __init__(self, name: str, version: str):
        self.name = name
        self.version = version


class Timeout:
    def __init__(self, duration: int, unit: str):
        self.duration = duration
        if unit not in ['SECONDS', 'MINUTES', 'HOURS', 'DAYS']:
            raise ValueError('invalid unit {0}'.format(unit))
        self.unit = unit

    def to_seconds(self):
        coefficient = 1
        if self.unit != 'SECONDS':
            coefficient *= 60
            if self.unit != 'MINUTES':
                coefficient *= 60
                if self.unit != 'HOURS':
                    coefficient *= 24
        return coefficient * self.duration


class Experiment:
    def __init__(
            self,
            name: str,
            parameters: List[str],
            disable: bool,
            timeout: Union[Timeout, None],
            level: int
    ):
        self.name = name
        self.parameters = parameters
        self.disable = disable
        self.timeout = timeout
        self.level = level


class Versioning:
    def __init__(self, repository: str, commit: str, authentication: bool):
        self.repository = repository
        self.commit = commit
        self.authentication = authentication


class Project:
    def __init__(
            self,
            comments: Union[str, None],
            path: str,
            requirements: List[Requirement],
            shortcuts: Dict[str, str],
            iterations: int,
            versioning: Versioning,
            compile: str,
            execute: str,
            experiments: List[Experiment],
            measures: List[str],
            stats: List[str],
            timeout: Timeout
    ):
        self.comments = comments
        self.path = path
        self.requirements = requirements
        self.shortcuts = shortcuts
        self.iterations = iterations
        self.versioning = versioning
        self.compile = compile
        self.execute = execute
        self.experiments = experiments
        self.measures = measures
        self.stats = stats
        self.timeout = timeout

    def restore(self, cmd: str) -> str:
        cmd = cmd.replace('{PROJECT}', self.path)
        shortcuts = self.shortcuts
        if shortcuts is None or len(shortcuts) == 0:
            return cmd
        else:
            while True:
                old = cmd
                for label, text in shortcuts.items():
                    cmd = cmd.replace('{' + label + '}', text)
                cmd = cmd.replace('{PROJECT}', self.path)
                if cmd == old:
                    break
            return cmd


def versioning_from_yml(yml) -> Versioning:
    return Versioning(
        yml['repository'],
        yml['commit'],
        bool(yml['authentication']) if 'authentication' in yml else False
    )


def experiment_from_yml(yml) -> Experiment:
    return Experiment(
        yml['name'],
        yml['parameters'],
        bool(yml['disable'] == 'true') if 'disable' in yml else None,
        timeout_from_yml(yml['timeout']) if 'timeout' in yml else None,
        int(yml['level']) if 'level' in yml else 0
    )


def timeout_from_yml(yml) -> Timeout:
    return Timeout(yml['duration'], yml['unit'])


def requirement_from_yml(yml) -> Requirement:
    return Requirement(yml['name'], yml['version'])


def project_from_file(f) -> Union[Project, None]:
    try:
        data = yaml.safe_load(f)
        return Project(
            data['comments'] if 'comments' in data else None,
            data['path'],
            list(map(requirement_from_yml, data['requirements'])) if 'requirements' in data else [],
            data['shortcuts'],
            int(data['iterations']),
            versioning_from_yml(data['versioning']) if 'versioning' in data else None,
            data['compile'],
            data['execute'],
            list(map(experiment_from_yml, data['experiments'])),
            data['measures'],
            data['stats'],
            timeout_from_yml(data['timeout']) if 'timeout' in data else None
        )
    except yaml.YAMLError as e:
        print(e)
        return None


def init(p: Project, folder):
    if not os.path.exists(p.path):
        os.makedirs(p.path)
    if not os.path.exists(folder):
        os.makedirs(folder)

    for experiment in p.experiments:
        exp_folder = folder + '/' + 'results' + '/' + experiment.name
        if not os.path.exists(exp_folder):
            os.makedirs(exp_folder)


def pull(p: Project):
    print('>> Fetching source')
    if p.versioning is None:
        raise ValueError('project versioning is not filled')

    path = project.path
    if os.path.exists(path) and not os.path.isdir(path):
        raise SystemError('{} is not a directory'.format(path))

    if len(os.listdir(path)) != 0:  # Source are already downloaded
        print(' | Some files are present in the source directory {}.\n'
              ' | Would you erase them and fetch the sources from the repository [y\\N]? '.format(path), end='')

        while True:
            response = input()
            if response in ['', 'y', 'Y', 'n', 'N']:
                break

        erase = response in ['y', 'Y']
        if erase:
            shutil.rmtree(path)
            os.makedirs(path)
        else:
            print('<< Cancel fetch source')
            return

    versioning = p.versioning
    git_cmd = 'git clone {} {}'.format(versioning.repository, path)
    if versioning.authentication:
        protocol = versioning.repository[:versioning.repository.index('://')]
        url = versioning.repository[versioning.repository.index('//') + 2:]
        username = quote(input(' | Username for {}: '.format(versioning.repository)))
        password = quote(getpass.getpass(' | Password for {}: '.format(versioning.repository)))
        git_cmd = 'git clone {}://{}:{}@{} {}'.format(
            protocol,
            username,
            password,
            url,
            path
        )
    if not safe_run(git_cmd):
        print('<< Exit fetching source')
        return

    checkout_cmd = 'git --git-dir {}/.git --work-tree {} checkout {}'.format(
        path,
        path,
        versioning.commit
    )
    safe_run(checkout_cmd)
    print('<< Fetching source')


def build(p: Project):
    build_cmd = p.restore(p.compile)
    print('>> Building executable')
    safe_run(build_cmd)
    print('<< Building executable')


def clean(folder: str):
    print('>> Cleaning old results')
    shutil.rmtree(folder + '/' + 'results')
    print(' | Done')
    print('<< Cleaning old results')


def fill(a: List[T], value: T):
    for i in range(len(a)):
        a[i] = value


class Stats:
    @staticmethod
    def min(values: List[int]) -> int:
        _min = values[0]
        for i in range(1, len(values)):
            if values[i] < _min:
                _min = values[i]
        return _min

    @staticmethod
    def max(values: List[int]) -> int:
        _max = values[0]
        for i in range(1, len(values)):
            if values[i] > _max:
                _max = values[i]
        return _max

    @staticmethod
    def first(values: List[int]) -> int:
        return values[0]

    @staticmethod
    def mean(values: List[int]) -> float:
        sum = 0
        for i in range(len(values)):
            sum += values[i]
        return sum / len(values)


def remove_nl(s: str) -> str:
    return s.replace('\n', '')


class CSV:
    @staticmethod
    def header(p: Project) -> str:
        header = 'experiments,'
        for measure in p.measures:
            if measure != 'skip':
                header += measure + ','
        for stat in project.stats:
            header += stat + ','
        header += '\n'
        return header

    @staticmethod
    def row(p: Project, exp: Experiment, log_file: Union[str, None], times: List[int]) -> str:
        row = '"' + exp.name + '",'

        timeout = None
        if p.timeout is not None:
            timeout = p.timeout
        if exp.timeout is not None:
            timeout = exp.timeout

        if log_file is not None and os.path.isfile(log_file):
            content = list(map(remove_nl, open(log_file, 'r').readlines()[-1].split(',')))
            for i in range(len(p.measures)):
                if p.measures[i] != 'skip' and len(content) > i:
                    row += content[i]
                row += ','

        for stat in p.stats:
            value = None
            if stat == 'min' or stat == 'MIN':
                value = Stats.min(times)
            elif stat == 'mean' or stat == 'MEAN' or stat == 'avg' or stat == 'AVERAGE':
                value = Stats.mean(times)
            elif stat == 'max' or stat == 'MAX':
                value = Stats.max(times)
            elif stat == 'time' or stat == 'TIME':
                value = Stats.first(times)
            else:
                print('Unknown stat {}'.format(stat))
            if value is None:
                row += 'nan'
            elif value < 0:
                row += 'error or timeout (> {} sec)'.format(timeout.to_seconds())
            else:
                row += str(value)
            row += ','

        for parameter in exp.parameters:
            row += str(parameter)
            row += ','

        return row + '\n'


def blue(s: str) -> str:
    return '\033[34m' + s + '\033[0m'


def red(s: str) -> str:
    return '\033[31m' + s + '\033[0m'


def yellow(s: str) -> str:
    return '\033[33m' + s + '\033[0m'


def execute(p: Project, folder: str, config_file_name: str):
    print('>> Running experiments')
    results_folder = folder + '/' + 'results'
    summary = results_folder + '/' + config_file_name + '.csv'
    if not os.path.exists(summary):
        with open(summary, 'a+') as summary_csv:
            summary_csv.write(CSV.header(p))
            summary_csv.close()

    for experiment in sorted(p.experiments, key=lambda it: it.level):
        exp_folder = results_folder + '/' + experiment.name
        if not os.path.exists(exp_folder):
            os.makedirs(exp_folder)
        lock_file = exp_folder + '/' + '_lock'
        if not os.path.exists(lock_file):
            open(lock_file, 'w+')
            now = datetime.datetime.now()
            print(' | Starting experiment [{}] @ {}'.format(experiment.name, now))

            times = [0 for _ in range(project.iterations)]

            for i in range(project.iterations):
                log_filename = exp_folder + '/' + str(i) + '.csv'

                timeout = None
                if project.timeout is not None:
                    timeout = project.timeout.to_seconds()
                if experiment.timeout is not None:
                    timeout = experiment.timeout.to_seconds()

                with open(log_filename, 'a+') as log_file:
                    skip_next = False
                    try:
                        start = datetime.datetime.now()
                        execution = project.restore(project.execute).split(' ') + list(map(str, experiment.parameters))
                        print('   | {}'.format(' '.join(execution)), end='\t')
                        subprocess.check_call(
                            execution,
                            stdout=log_file,
                            stderr=subprocess.STDOUT,
                            timeout=timeout
                        )
                        end = datetime.datetime.now()
                        times[i] = (end - start).seconds
                        print('[' + blue('V') + ']')
                    except subprocess.TimeoutExpired:
                        fill(times, -1)
                        log_file.write('Timeout of {} seconds\n\n'.format(timeout))
                        print('[' + yellow('T') + ']')
                        skip_next = True
                    except subprocess.CalledProcessError as c:
                        fill(times, -1)
                        log_file.write('Subprocess error {}\n\n'.format(c))
                        print('[' + red('E') + ']')
                        skip_next = True
                    log_file.close()
                    if skip_next:
                        break

            with open(summary, 'a+') as summary_csv:
                summary_csv.write(CSV.row(p, experiment, exp_folder + '/0.csv', times))
                summary_csv.close()

    print('<< Running experiments')


if __name__ == '__main__':
    path: str = sys.argv[1]
    folder = path[:path.rindex('.')]
    config_filename = folder[folder.rindex('/') + 1:]

    with open(path) as stream:
        project = project_from_file(stream)
        project.path = project.path.replace('{FILE}', folder)

        if len(sys.argv) == 2:
            print('Project requirements: ')
            for requirement in project.requirements:
                print(' - {} >= {}'.format(requirement.name, requirement.version))
            print()
            print('Commands: ')
            print(' -g or --git:\t Retrieves the sources from the remote repository (if exists)')
            print(' -b or --build:\t Compile the project')
            print(
                ' -r or --run:\t Run the experiments. The summary file will be located in {}'
                    .format(project.path + '/results')
            )
            print(' --clean:\t Clean the results folder')
            print()
            if project.comments is not None:
                print('Notes: ')
                print(project.comments)

        verbose = '-v' in sys.argv or '--verbose' in sys.argv
        init(project, folder)

        if '-g' in sys.argv or '--git' in sys.argv:
            pull(project)

        if '-b' in sys.argv or '--build' in sys.argv:
            build(project)

        if '--clean' in sys.argv:
            clean(folder)
            init(project, folder)

        if '-r' in sys.argv or '--run' in sys.argv:
            execute(project, folder, config_filename)
