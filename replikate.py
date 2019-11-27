#!/usr/bin/python3
import base64
import csv
import datetime
import getpass
import os
import shutil
import smtplib
import ssl
import subprocess
import urllib.request
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
from urllib.parse import quote
from typing import Dict, List, Union, TypeVar, Tuple

import yaml
import sys

T = TypeVar('T')


def safe_run(cmd: str) -> bool:
    status = subprocess.call(cmd.split(' '))
    if status != 0:
        print(' | Fail to run cmd: {}'.format(cmd))
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


class ServerParameters:
    def __init__(
            self,
            host: str,
            port: int,
            authentication: Union[str, None]
    ):
        self.host = host
        self.port = port
        if authentication not in [None, 'STARTTLS', 'SSL/TLS']:
            raise ValueError('Invalid authentication mode {}'.format(authentication))
        self.authentication = authentication


class MailAccount:
    def __init__(
            self,
            user_name: str,
            mail: str
    ):
        self.user_name = user_name
        self.mail = mail


class EMailer:
    def __init__(
            self,
            server_parameters: ServerParameters,
            mail_account: MailAccount
    ):
        self.server_parameters = server_parameters
        self.mail_account = mail_account
        self.pwd = None
        if server_parameters.authentication is not None:
            print(' | Required password for sending mail')
            self.pwd = getpass.getpass(' | Password for {}@{}: '.format(mail_account.user_name, server_parameters.host))

    def send_mail(self, receivers: List[str], subject: str, message: str, files: List[Tuple[str, str]] = []):
        if self.server_parameters.authentication == 'STARTTLS':
            context = ssl.create_default_context()
            try:
                with smtplib.SMTP(self.server_parameters.host, self.server_parameters.port) as smtp:
                    smtp.starttls(context=context)
                    smtp.login(
                        self.mail_account.user_name,
                        self.pwd
                    )
                    mail = MIMEMultipart()
                    mail['From'] = self.mail_account.mail
                    mail['To'] = ', '.join(receivers)
                    mail['Date'] = formatdate(localtime=True)
                    mail['Subject'] = subject
                    mail.attach(MIMEText(message, 'html'))
                    for (f, name) in files:
                        part = MIMEBase('application', 'octet-stream')
                        part.set_payload(open(f, 'rb').read())
                        encoders.encode_base64(part)
                        part.add_header('Content-Disposition', 'piece; filename= %s' % name)
                        mail.attach(part)

                    smtp.sendmail(
                        self.mail_account.mail,
                        receivers,
                        mail.as_string()
                    )
            except smtplib.SMTPException as e:
                print('Cannot send email')


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


class HTML:
    @staticmethod
    def header(p: Project) -> str:
        header = '<tr><th>experiments</th>'
        for measure in p.measures:
            if measure != 'skip':
                header += '<th>' + measure + '</th>'
        for stat in project.stats:
            header += '<th>' + stat + '</th>'
        header += '<th>arguments</th>'
        header += '</tr>'
        return header

    @staticmethod
    def from_csv_file(file):
        html = '<table>'
        with open(file, 'r') as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=',', quotechar='"')
            is_header = True
            for row in csv_reader:
                html += '<tr>'
                tag = 'td'
                end = ''
                if is_header:
                    is_header = False
                    tag = 'th'
                    end = '</th><th>arguments'
                html += '<' + tag + '>'
                html += ('</' + tag + '><' + tag + '>').join(row)
                html += end
                html += '</' + tag + '></tr>'

        html += '</table>'
        return html

    @staticmethod
    def row(p: Project, exp: Experiment, log_file: Union[str, None], times: List[int]) -> str:
        row = '<tr><td>' + exp.name + '</td>'

        timeout = None
        if p.timeout is not None:
            timeout = p.timeout
        if exp.timeout is not None:
            timeout = exp.timeout

        if log_file is not None and os.path.isfile(log_file):
            content = list(map(remove_nl, open(log_file, 'r').readlines()[-1].split(',')))
            for i in range(len(p.measures)):
                row += '<td>'
                if p.measures[i] != 'skip' and len(content) > i:
                    row += content[i]
                row += '</td>'

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
            if times[0] == -2:
                row += '<td>error</td>'
            elif times[0] == -1:
                row += '<td>timeout (> {} sec)</td>'.format(timeout.to_seconds())
            elif value is None:
                row += '<td>nan</td>'
            else:
                row += '<td>' + str(value) + '</td>'

        row += '<td>'
        for parameter in exp.parameters:
            row += str(parameter)
            row += '&nbsp;&nbsp;&nbsp;&nbsp;'
        row += '</td>'
        return row + '</tr>'


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
            if times[0] == -1:
                row += 'timeout (> {} sec)'.format(timeout.to_seconds())
            elif times[0] == -2:
                row += 'error'
            elif value is None:
                row += 'nan'
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


def execute(
        p: Project,
        folder: str,
        config_file_name: str,
        emailer: Union[EMailer, None],
        email_args: Dict[str, Union[str, List[str]]]
):
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
                        print('   > {}'.format(' '.join(execution)), end='\t', flush=True)
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
                        log_file.flush()
                        print('[' + yellow('T') + ']')

                        if email_args['on_timeout'] in ['first', 'always'] and emailer is not None:
                            emailer.send_mail(
                                email_args['to'],
                                'Experiment {} timeout'.format(experiment.name),
                                '<html><body>'
                                '<h1>' + experiment.name + '</h1>' +
                                '<table>' +
                                HTML.header(p) +
                                HTML.row(p, experiment, exp_folder + '/' + str(i) + '.csv', times) +
                                '</table>'
                                '</body></html>',
                                files=[(exp_folder + '/' + str(i) + '.csv', 'log')]
                            )
                            if email_args['on_timeout'] == 'first':
                                email_args['on_timeout'] = 'never'

                        skip_next = True
                    except subprocess.CalledProcessError as c:
                        fill(times, -2)
                        log_file.write('Subprocess error {}\n\n'.format(c))
                        log_file.flush()
                        print('[' + red('E') + ']')

                        if email_args['on_failure'] in ['first', 'always'] and emailer is not None:
                            emailer.send_mail(
                                email_args['to'],
                                'Experiment {} has failed'.format(experiment.name),
                                '<html><body>'
                                '<h1>' + experiment.name + '</h1>' +
                                '<table>' +
                                HTML.header(p) +
                                HTML.row(p, experiment, exp_folder + '/' + str(i) + '.csv', times) +
                                '</table>'
                                '</body></html>',
                                files=[(exp_folder + '/' + str(i) + '.csv', 'log')]
                            )
                            if email_args['on_failure'] == 'first':
                                email_args['on_failure'] = 'never'

                        skip_next = True
                    log_file.close()
                    if skip_next:
                        break

                if email_args['frequency'] == 'each' and emailer is not None:
                    emailer.send_mail(
                        email_args['to'],
                        'Experiment {} end'.format(experiment.name),
                        '<html><body>'
                        '<h1>' + experiment.name + '</h1>' +
                        '<table>' +
                        HTML.header(p) +
                        HTML.row(p, experiment, exp_folder + '/' + str(i) + '.csv', times) +
                        '</table>'
                        '</body></html>',
                        []
                    )

            with open(summary, 'a+') as summary_csv:
                summary_csv.write(CSV.row(p, experiment, exp_folder + '/0.csv', times))
                summary_csv.close()

    files = []
    if 'summary' in email_args['attach']:
        files.append((summary, 'summary.csv'))
    if email_args['frequency'] == 'end' and emailer is not None:
        comments = p.comments if p.comments is not None else 'None'
        emailer.send_mail(
            email_args['to'],
            'Experiment %s end' % config_file_name,
            '<html><body>' +
            '<h1>' + config_file_name + '</h1>' +
            'Description: <br/><pre><code>' +
            comments +
            '</code></pre>' +
            HTML.from_csv_file(summary) +
            '</body></html>',
            files
        )

    print('<< Running experiments')


def generate_file(p: Project, config_file_name: str, model: str):
    hash = subprocess.check_output('git rev-parse --verify HEAD'.split(' '))
    hash = hash.decode('UTF-8').replace('\n', '')
    short_hash = hash[:6]
    print('\\begin{{model}}[{} {}] \\label{{md:{}:{}}}'
        .format(
            model.replace('_', ' '),
            short_hash,
            config_file_name[:config_file_name.rindex('.')][config_file_name.rindex('/')+1:].replace('_', '-'),
            short_hash
        )
    )
    print('\\configfile{{{}}}{{{}}}'.format(hash, config_file_name.replace('_', '\\_')))
    print(p.comments)
    print('\\end{model}')


def emailer_from_file(f) -> Union[EMailer, None]:
    try:
        data = yaml.safe_load(f)
        return EMailer(
            server_parameters_from_yml(data['server']),
            mail_account_from_yml(data['mail_account'])
        )
    except yaml.YAMLError as e:
        print(e)
        return None


def server_parameters_from_yml(yml) -> ServerParameters:
    return ServerParameters(
        yml['host'],
        int(yml['port']),
        yml['authentication']
    )


def mail_account_from_yml(yml) -> MailAccount:
    return MailAccount(
        yml['username'],
        yml['mail']
    )


def init_mail(email_args: Dict[str, str]) -> Union[EMailer, None]:
    if not os.path.exists(email_args['config']):
        print('The configuration file %s for sending email is not present' % email_args['config'])
        cancel_emails = input('If you continue, the emails will not be send during the execution [Y\\n]? ')
        while cancel_emails not in ['', 'y', 'Y', 'n', 'N']:
            cancel_emails = input('If you continue, the emails will not be send during the execution [Y\\n]? ')
        if cancel_emails in ['', 'y', 'Y']:
            return None
        raise ValueError('Unknown configuration file %s' % email_args['config'])

    with open(email_args['config'], 'r') as email_config_file:
        return emailer_from_file(email_config_file)


def is_email_arg(s: str) -> bool:
    return s.startswith('--mail:')


def clean_mail_args(s: str) -> (str, str):
    return s[7:].split('=')


if __name__ == '__main__':
    path: str = sys.argv[1]
    if path.startswith("url="):
        print('>> Loading remote configuration')
        repo = path[5:path.index(']')]
        if repo[-1] == '/':
            repo = repo[:-1]
        path = path[path.index(']')+1:]
        if os.path.exists(path):
            print('  The file {} already exist, would you erase it ? [y/N]:'.format(path), end='')
            text = input()
            while text not in ["", "y", "Y", "n", "N"]:
                text = input()
            if text in ['y', 'Y']:
                urllib.request.urlretrieve(repo + '/' + path, path)
            else:
                print('  Loading aborted, the script will use the local file')
        else:
            urllib.request.urlretrieve(repo + '/' + path, path)
        print('<< Loading remote configuration')

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
            print(' --mail: Configure the automatic email sending. ex --email:to=me@my-mail.com --email:frequency=each')
            print('    to: add an email to the recipients')
            print('    frequency: send an email foreach experiment (each) or when the full summary is complete (end).')
            print('    on_failure: indicates whenever an email must be send when an experiment fails, '
                  'valid options are [never, first, always]')
            print('    on_timeout: indicates whenever an email must be send when an experiment produces a timeout, '
                  'valid options are [never, first, always]')
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

        email_args = list(map(clean_mail_args, filter(is_email_arg, sys.argv)))
        mail_params = {
            'to': [],
            'frequency': 'never',
            'on_failure': 'never',
            'on_timeout': 'never',
            'attach': [],
            'config': 'account.yml'
        }
        emailer = None
        if len(email_args) != 0:
            for (key, value) in email_args:
                if key in ['to', 'attach']:
                    mail_params[key].append(value)
                elif key in ['on_failure', 'on_timeout', 'frequency', 'config']:
                    mail_params[key] = value
                else:
                    print('invalid mail configuration argument: %s' % key)
            emailer = init_mail(mail_params)

        if '-r' in sys.argv or '--run' in sys.argv:
            execute(project, folder, config_filename, emailer, mail_params)

        file_generation = list(filter(lambda arg: arg.startswith('--file='), sys.argv))
        if len(file_generation) == 1:
            generate_file(project, path, file_generation[0][7:])
