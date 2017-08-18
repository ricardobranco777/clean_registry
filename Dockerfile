FROM	registry:2

RUN	apk --no-cache add python3 python3-dev

RUN	pip3 install --no-cache-dir docker docker[tls] pyyaml

COPY	clean_registry.py /usr/local/bin/clean_registry.py

RUN	python3 -OO -m compileall /usr/local/bin/clean_registry.py

ENTRYPOINT ["/usr/bin/python3", "/usr/local/bin/clean_registry.py"]
CMD	[]
