
# docker build -t chopper .
# docker run -it chopper bash
# docker run -it --mount type=bind,source="$(pwd)",target=/home/sm/app chopper bash
# see docker-compose.yaml for commands that supersede these ^.

FROM python:3.9-slim

ARG USER=sm

RUN apt-get update;

RUN <<EOF
    set -eux;
    apt-get install --yes sudo joe git;
    useradd --create-home $USER --password "$(openssl passwd -1 password)";
    usermod -aG sudo $USER;
EOF

USER $USER

WORKDIR /home/$USER/chopper

ENV VIRTUAL_ENV_DISABLE_PROMPT=1

# allows docker to cache python packages
ENV PIP_NO_CACHE_DIR=1

RUN <<EOF
    set -eux;
    PATH=$HOME/.local/bin:$PATH;
    echo "PS1='\n\[\033[01;32m\]\$VIRTUAL_ENV_PROMPT\[\033[00m\] \[\033[01;35m\]\u@\h\[\033[00m\] \[\033[01;34m\]\w\[\033[00m\]\n\$ '" >> $HOME/.bashrc;
    echo 'PATH=$HOME/.local/bin:$PATH' >> $HOME/.bashrc;
    echo 'alias ll="ls -lhAF --color=always --group-directories-first"' >> $HOME/.bashrc;
    echo 'alias ls="ls -AF --color=always --group-directories-first"' >> $HOME/.bashrc;
EOF

RUN python3 -m pip install --user pipx;
RUN python3 -m pipx ensurepath;
RUN python3 -m pipx completions;
RUN /home/sm/.local/bin/pipx install poetry;
RUN /home/sm/.local/bin/poetry completions bash >> ~/.bash_completion;
