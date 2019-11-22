# Loïc Rouquette PhD experiments

## Requirements
- gradle >= 4.9
- java >= 1.8

## How to run
The execution is simple, open a terminal at the root of the repository and run:
```bash
./replikate.py path_to_config.yml -g -b -r
```

The option `-g` will fetch the source code from the repository
The option `-b` will build the jar file
The option `-r` will run the experiment

!! Running the experiment will lock the folder to prevent results erasure. To clean the old result, use the `--clean` option before rerun the option `r`.

Usage example:
```bash
./replikate.py public/summary_nov_19.yml -g -b -r
```

If you do not specify command, like: `./replikate.py public/summary_nov_19.yml`, the script will display the description of the configuration file and the command line help.
Example: 
```markdown
Project requirements: 
 - gradle >= 4.9
 - java >= 1.8

Commands: 
 -g or --git:	 Retrieves the sources from the remote repository (if exists)
 -b or --build:	 Compile the project
 -r or --run:	 Run the experiments. The summary file will be located in public/summary_nov_19/aes_advanced_gerault/src/results
 --clean:	 Clean the results folder
 --mail: Configure the automatic email sending. ex --email:to=me@my-mail.com --email:frequency=each
    to: add an email to the recipients
    frequency: send an email foreach experiment (each) or when the full summary is complete (end).
    on_failure: indicates whenever an email must be send when an experiment fails, valid options are [never, first, always]
    on_timeout: indicates whenever an email must be send when an experiment produces a timeout, valid options are [never, first, always]

Notes: 
## AES Step 1

Model: AES Advanced [1]
Heuristic : Dom/WDeg (standard version)

Heuristic splits : [$\Delta$SBoxes, abstractVars*]
*abstractVars = [$\Delta X$, $\Delta K$, $\Delta Z$] and $\Delta Y$ are a combination of $\Delta$SBoxes.

[1] David Gérault, Pascal Lafourcade, Marine Minier, Christine Solnon. Revisiting AES Related-Key
    Differential Attacks with Constraint Programming. Information Processing Letters, Elsevier, 2018,
    139, pp.24-29
```

## Folders
When an experiment is performed, a new folder is created with the name of the experiment file. Ex: `my_conf.yml` will create a new folder `my_conf` at the same path.
The source files will be downloaded under `my_conf/src` and the results files will be printed under `my_conf/results`. A summary csv will be avaible at the root of the results folder, and foreach experiment a new folder will be printed with the log of the run. The _lock files are only used to prevent the reexecution of the same experiment when the script is launched multiple times.