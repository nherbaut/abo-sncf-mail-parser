from ubuntu
RUN apt-get update
RUN apt-get install python3 python3-pip --yes
COPY requirements.txt /root
RUN pip3 install -r /root/requirements.txt
run apt-get install vim --yes
COPY . /root/rsctoy
WORKDIR /root/rsctoy

