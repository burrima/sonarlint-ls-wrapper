# sonarlint-ls-wrapper
Prototype to connect sonarlint language-server to Vim-ALE

## Introduction

A good linter is essential in nowadays professional work environments. There are
already many options available to be used with Vim through the ALE plugin
(https://github.com/dense-analysis/ale). However, a very popular one, sonarlint,
is not yet supported.

Sonarlint is supporting the commonly used language server protocol (also
supported by Vim/ALE), but with some problems that make it impossible to be
used out-of-the-box with Vim (see below).

The script `sonarlint-ls-wrapper` in this repository was developed as a rescue
to make it work. The script acts as language server wrapper, talking to Vim/ALE
and to sonarlint to make the two compatible to each other. The goal of this
script is to provide an intermediate solution until proper integration is done
(though it is unclear if this will ever happen).

The script is tested with the following languages:
  * C++
  * Python

Other languages might work equally well - but maybe some extensions to the
script are required. Please let me know when you got other languages working.

## Installation

### Preconditions
The following preconditions apply:
  * Linux operating system
  * Python >=3.6 installed
  * Vim with ALE (https://github.com/dense-analysis/ale) installed
  * VSCode installed (including sonarlint plugin)

You might have success with other means of sonarlint installation, but the
script was developed with the VSCode plugin as base.

### Step 1: find the sonarlint binary and update the script
You need to provide the correct `SONARLINT_PATH` and `SONARLINT_START_CMD`
variables directly in the script. To find out the correct values, run VSCode
(with the sonarlint plugin installed), open a source file and issue `ps aux |
grep sonarlint` on the command line. This should show you the correct command.

### Step 2: extend your vimrc
The file `vimrc-template` in this repository contains code which needs to be
placed into the `.vimrc` file in your home folder. This code adds a new linter
called 'sonarlint' to Vim/ALE.

Important: provide the correct path to the script via the variable
`s:sonarlint_wrapper_executable`.

## The Problem with sonarlint and Vim

The sonarlint language server does not work out-of-the-box with Vim. There are
the following seven problems which are addressed by this script.

### Problem 0: inverted socket logic
Vim/ALE provides the possibility to work with language servers through TCP.
However, the expectation is that the language server provides a socket where ALE
can connect to. Furthermore, it is unclear to me how the language server is
started and stopped.

Thus, the script `sonarlint-ls-wrapper` provides a stdio interface for ALE. On
the other end, the script provides a server socket and starts/stops the
sonarlint binary automatically. The sonarlint connects to the provided socket.

The implementation is not very robust as socket ports are currently chosen
randomly. We cannot use the same port each time as different Vim buffers may run
sonarlint in parallel.

### Problem 1: missing clientInfo in initialize message
Vim/ALE does not provide the key "clientInfo" in the initialize message, but
sonarlint is expecting it. It wont' work without.

Thus, the script listens for the initialize message from ALE and extends it with
this information.

### Problem 2: missing window options in initialize message
Vim/ALE does not provide the "window" options in the initialize message. Also
here, sonarlint refuses to work without.

Thus, the script listens for the initialize message from ALE and extends it with
this information.

### Problem 3: ALE not responding to config request message
Vim/ALE does not respond to the config request message sent by sonarlint. But
luckily, the config is provided earlier through the 'didChangeConfiguration'
message.

The script stores the initial configuration and provides it to sonarlint again
when it is asking for it.

### Problem 4: proprietary requests 'isOpenInEditor' not supported by ALE
Vim/ALE does not know the proprietary request 'isOpenInEditor' and refuses to
answer to it. But sonarlint stops without this information.

Thus, the script just replies with True, assuming that the file is opened.

### Problem 5: proprietary request 'isIgnoredByScm' not supported by ALE
Vim/ALE does not know the proprietary request 'isIgnoredByScm' and refuses to
answer to it. But sonarlint stops without this information.

Thus, the script just replies with False, assuming that the file is under
version control (SCM = Source Code Management).

### Problem 6: sonarlint diagnostics making Vim hang for a while
Sonarlit starts sending the identified diagnostics continuously towards Vim.
This is confusing Vim and keeping it busy updating the buffer. The user
experiences a very slow (or even hanging) Vim.

It is sufficient to send the final message containing all findings. Thus, the
script buffers all diagnostics messages until it gets a special logging message
from sonarlint. Only then the diagnostics are forwarded to Vim. This is also not
very robust, but at least it stops Vim from hanging.

## Contributing
The code in this repository is licensed under the BSD-2 license, which is very
permissive and allows you to change the code without reaching out to me.
However, I would really appreciate if you give me a notice and send me your
changes, in case you make some progress or find any bugs. This should be a
collaborative work.

## A word to the maintainers of sonarlint and Vim/ALE
The code in this repository is basically a proof-of-concept to bring Vim and
sonarlint together. Let me know if I could support you in any activities. I
would love to see sonarlint being native supported by Vim/ALE.
