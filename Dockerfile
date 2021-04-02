FROM	registry:2

COPY	requirements.txt /tmp

RUN	apk --no-cache add --virtual .build-deps \
		gcc \
		libffi-dev \
		make \
		musl-dev \
		openssl-dev \
		python3-dev && \
	apk --no-cache add python3 && \
	pip3 install --no-cache-dir --upgrade pip && \
	pip3 install --compile --no-cache-dir -r /tmp/requirements.txt && \
	apk del .build-deps

COPY	clean_registry.py /usr/local/bin/clean_registry.py

RUN	python3 -OO -m compileall /usr/local/bin/clean_registry.py

ENTRYPOINT ["/usr/bin/python3", "/usr/local/bin/clean_registry.py"]
CMD	[]
