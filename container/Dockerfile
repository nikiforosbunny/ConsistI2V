FROM pytorch/pytorch:latest

WORKDIR app

# vi mode
RUN echo "set -o vi" > /root/.bashrc
RUN echo 'set editing-mode vi' > /root/.inputrc

RUN apt-get update
RUN apt-get install -y git vim

RUN git clone --branch feature/rest-api-functionality https://github.com/nikiforosbunny/ConsistI2V /app

WORKDIR /app/
RUN python -m pip install -r pip_requirements.txt
RUN python -m pip install -r requirements_worker.txt
RUN bash download_models.sh $(which python) "cpu"

# download models

CMD ["python", "run_consumer.py"]
