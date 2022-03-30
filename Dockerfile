FROM	registry:2

COPY	requirements.txt /tmp/

RUN	apk --no-cache add --virtual .build-deps \
		cargo \
		gcc \
		libffi-dev \
		make \
		musl-dev \
		py3-pip \
		python3-dev \
		rust && \
	apk --no-cache add python3 && \
	pip install --no-cache-dir --upgrade pip && \
	pip install --compile --no-cache-dir -r /tmp/requirements.txt && \
	apk del .build-deps

COPY	clean_registry.py /usr/local/bin/clean_registry.py

RUN	python3 -OO -m compileall /usr/local/bin/clean_registry.py

ENTRYPOINT ["/usr/bin/python3", "/usr/local/bin/clean_registry.py"]
CMD	[]
