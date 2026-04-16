# Dockerfile that builds a fully functional image of openeduarchive.
#
# This image installs all Python dependencies for your application. It's based
# on Almalinux (https://github.com/inveniosoftware/docker-invenio)
# and includes Pip, Pipenv, Node.js, NPM and some few standard libraries
# Invenio usually needs.
#
# Used by Github actions to build the image and push it to the local registry.


FROM registry.cern.ch/inveniosoftware/almalinux:1

COPY site ./site
COPY Pipfile Pipfile.lock ./
RUN pipenv install --deploy --system

COPY ./docker/uwsgi/ ${INVENIO_INSTANCE_PATH}
COPY ./invenio.cfg ${INVENIO_INSTANCE_PATH}
COPY ./templates/ ${INVENIO_INSTANCE_PATH}/templates/
COPY ./app_data/ ${INVENIO_INSTANCE_PATH}/app_data/
COPY ./translations/ ${INVENIO_INSTANCE_PATH}/translations/
COPY ./ .

# Patch for https://github.com/inveniosoftware/invenio-records-resources/pull/663
# KeyError in facets label_map when a resource type exists in OpenSearch but not in vocabulary
RUN sed -i 's/"label": label_map\[key\]/"label": label_map.get(key, key)/g' /usr/local/lib/python3.9/site-packages/invenio_records_resources/services/records/facets/facets.py

RUN cp -r ./static/. ${INVENIO_INSTANCE_PATH}/static/ && \
    cp -r ./assets/. ${INVENIO_INSTANCE_PATH}/assets/ && \
    invenio collect --verbose  && \
    invenio webpack buildall

ENTRYPOINT [ "bash", "-c"]
