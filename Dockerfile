FROM python:3.9-buster AS build

WORKDIR /opt/setup/

COPY . .

RUN pip install .

FROM python:3.9-slim-buster
COPY --from=build /usr/local/lib/python3.9/site-packages /usr/local/lib/python3.9/site-packages
COPY --from=build /usr/local/bin/kube-event-pipe /usr/local/bin/kube-event-pipe

RUN useradd user --no-create-home -u 12341
# For persistent filters, use a volume.
RUN mkdir /var/filters && chown user /var/filters
ENV KUBE_EVENT_PIPE_PERSISTENCE_PATH=/var/filters

USER user
CMD kube-event-pipe
