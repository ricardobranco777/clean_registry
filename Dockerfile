FROM	registry:2

COPY	requirements.txt /tmp

RUN	apk --no-cache add \
		gcc \
		libc-dev \
		libffi-dev \
		make \
		openssl-dev \
		python3-dev \
		python3 && \
	pip3 install --no-cache-dir --upgrade pip && \
	pip3 install --no-cache-dir -r /tmp/requirements.txt && \
	apk del \
		gcc \
		libc-dev \
		libffi-dev \
		make \
		openssl-dev \
		python3-dev

COPY	clean_registry.py /usr/local/bin/clean_registry.py

RUN	python3 -OO -m compileall /usr/local/bin/clean_registry.py

ENTRYPOINT ["/usr/bin/python3", "/usr/local/bin/clean_registry.py"]
CMD	[]
