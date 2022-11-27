# sonarlint-ls-wrapper
Prototype to connect SonarLint language-server to Vim-ALE

## Introduction

A good linter is essential in nowadays professional work environments. There are
already many options available to be used with Vim through the ALE plugin
(https://github.com/dense-analysis/ale). However, SonarLint
(https://www.sonarsource.com/products/sonarlint/) is not yet supported.

It is straight-forward and well documented how to add new linters to ALE - given
that the linter itself fulfills some requirements. SonarLint is unfortunately
not compatible with ALE (exact versions tested see below). It supports the
commonly used language-server protocol but there are some caveats hindering the
two parties to work with each other. Details are listed below.

The script `sonarlint-ls-wrapper.py` in this repository was developed as a
rescue to make it work. The script acts as a wrapper around SonarLint to make it
compatible to ALE. The goal of this script is to provide an intermediate
solution until proper integration is done (though it is unclear if this will
ever happen).

## Tested Combinations of ALE and SonarLint

  * SonarLint for VSCode from GitHub: SonarSource/sonarlint-language-server
  * ALE from GitHub: dense-analysis/ale

| SonarLint              | ALE      | sonarlint-ls-server |
|------------------------|----------|---------------------|
| (VSCode) v2.11.0.54859 | 3.2.0    | 0.1.0               |

The script `sonarlint-ls-wrapper.py` is tested with the following languages:
  * C++
  * Python

Other languages might work equally well - but maybe some extensions to the
script are required. Please let me know when you got other languages working.

## Installation

This section explains how to setup everything to make it work.

### Preconditions
The following preconditions apply:
  * Linux operating system
  * Python >=3.6 installed
  * Vim with ALE installed
  * VSCode installed (including SonarLint plugin)

You might have success with other means of SonarLint installation, but the
script was developed and tested with the VSCode plugin as base.

### Step 1: find the SonarLint binary and update the script
You need to provide the correct `SONARLINT_PATH` and `SONARLINT_START_CMD`
variables directly in the script. To find out the correct values, run VSCode
(with the SonarLint plugin installed), open a source file and issue `ps aux |
grep sonarlint` on the command line. This should show you the correct command.

### Step 2: extend your vimrc
The file `vimrc-template` in this repository contains code which needs to be
placed into the `.vimrc` file in your home folder. This code adds a new linter
called 'sonarlint' to Vim/ALE.

Important: provide the correct path to the script via the variable
`s:sonarlint_wrapper_executable`.

## The Problem with SonarLint and Vim

The SonarLint language server does not work out-of-the-box with Vim. There are
the following problems which are addressed by this project.

### Problem 0: inverted socket logic and unclear lifetime
ALE already provides the possibility to work with language servers through the
TCP protocol. However, the expectation is that the language server provides a
socket where ALE can connect to. But this is not provided by SonarLint as it
expects by its own to connect as a client to a server socket. I've had initial
success to make both talk to each other with the following command (on Alma
Linux 8):

  * `nc -k -l --broker -vvv 5000`

Unfortunately, talking to each other does not automatically mean "understanding
each other" - there are other issues. But at least the option `-vvv` provides
good insight into the exchanged messages.

It is also unclear to me how the language server is started and stopped by ALE
when it is running as stand-alone service. Probably, the idea is that it shall
run all the time in the background. Here, I need to dig a bit further.

Anyway, I found it to be more aligned with other language servers to use the
stdio interface of ALE and to let ALE start and stop SonarLint automatically
when needed. This is also aligned with VSCode which is taking responsibility
over the lifetime of SonarLint. Thus, the script `sonarlint-ls-wrapper.py`
provides a stdio interface towards ALE. On the other end, the script provides a
server socket and starts/stops the SonarLint binary automatically. The SonarLint
connects to the provided socket.

The implementation is not very robust as socket ports are currently chosen
randomly. We cannot use the same port each time as different Vim buffers may run
SonarLint in parallel.

### Problem 1: missing clientInfo in initialize message
ALE does not provide the key `clientInfo` in the initialize message, but
SonarLint is expecting it. It wont' work without.

Thus, the script listens for the initialize message from ALE and extends it with
this information.

### Problem 2: missing window options in initialize message
ALE does not provide the "window" options in the initialize message. Also
here, SonarLint refuses to work without.

Thus, the script listens for the initialize message from ALE and extends it with
this information.

### Problem 3: ALE not responding to config request message
ALE does not respond to the config request message sent by SonarLint. But
luckily, the config is provided earlier through the `didChangeConfiguration`
message.

The script stores the initial configuration and provides it to SonarLint again
when it is asking for it.

### Problem 4: proprietary requests 'isOpenInEditor' not supported by ALE
ALE does not know the proprietary request `isOpenInEditor` and refuses to
answer to it. But SonarLint stops without this information.

Thus, the script just replies with True, assuming that the file is opened.

### Problem 5: proprietary request 'isIgnoredByScm' not supported by ALE
ALE does not know the proprietary request `isIgnoredByScm` and refuses to
answer to it. But SonarLint stops without this information.

Thus, the script just replies with False, assuming that the file is under
version control (SCM = Source Code Management).

### Problem 6: SonarLint diagnostics making Vim hang for a while
Sonarlit starts sending the identified diagnostics continuously towards ALE.
This is confusing Vim and keeping it busy updating the buffer. The user
experiences a very slow (or even hanging) Vim.

It is sufficient to send the final message containing all findings. Thus, the
script buffers all diagnostics messages until it gets a special logging message
from SonarLint. Only then the diagnostics are forwarded to Vim. This is also not
very robust, but at least it stops Vim from hanging.

## Contributing
The code in this repository is licensed under the BSD-2 license, which is very
permissive and allows you to change the code without reaching out to me.
However, I would really appreciate if you give me a notice and send me your
changes, in case you make some progress or find any bugs. This should be a
collaborative work.

To log the exchanged language-server messages, set the variable `LOGFILE` in the
script `sonarlint-ls-wrapper.py` to any file path (e.g.
"/tmp/sonarlint-ls-wrapper.log". This will make the script to log all messages
to this file. If enabled, it is recommended to work with only 1 source file at a
time as there is no interlocking between different instances. Logging should be
off by default.

## A word to the maintainers of SonarLint and Vim/ALE
The code in this repository is basically a proof-of-concept to bring Vim and
SonarLint together. Let me know if I could support you in any activities. I
would love to see SonarLint being native supported by Vim/ALE.

## Actions taken so far
The following actions have been taken so far to improve the situation:

  * Implement this wrapper and write documentation about it
  * Reply on SonarLint communit blog: https://community.sonarsource.com/t/running-sonarlint-language-server-from-shell/24440

## Planned next steps
  * Submit the idea of Vim integration towards Sonar: https://www.sonarsource.com/products/sonarlint/roadmap/
  * Submit the idea towards the ALE maintainers
  * Try to support further programming languages which are supported by SonarLint
