FROM	registry:2

COPY	requirements.txt /tmp/

# NOTE: To build on other platforms also add: gcc libffi-dev musl-dev python3-dev
RUN	apk --no-cache add python3 py3-pip && \
	pip install --compile --no-cache-dir -r /tmp/requirements.txt

COPY	clean_registry.py /usr/local/bin/clean_registry.py

RUN	python3 -OO -m compileall /usr/local/bin/clean_registry.py

ENTRYPOINT ["/usr/bin/python3", "/usr/local/bin/clean_registry.py"]
CMD	[]
