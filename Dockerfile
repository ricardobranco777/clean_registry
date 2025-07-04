FROM	registry:3

RUN	apk --no-cache add python3

COPY	clean_registry.py /usr/local/bin/clean_registry.py

ENTRYPOINT ["/usr/bin/python3", "/usr/local/bin/clean_registry.py"]
CMD	[]
