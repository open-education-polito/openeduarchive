# Dockerfile that builds a fully functional image of your app.
#
# This image installs all Python dependencies for your application. It's based
# on Almalinux (https://github.com/inveniosoftware/docker-invenio)
# and includes Pip, Pipenv, Node.js, NPM and some few standard libraries
# Invenio usually needs.
#
# Note: It is important to keep the commands in this file in sync with your
# bootstrap script located in ./scripts/bootstrap.

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

# Patch for WTForms 3.x compatibility in invenio_oauth2server
# iter_choices() returns 4 values in WTForms 3.x instead of 3
RUN sed -i 's/for val, label, selected in field.iter_choices()/for val, label, selected, *_ in field.iter_choices()/g' /usr/local/lib/python3.9/site-packages/invenio_oauth2server/theme/semantic/form_styling.py

RUN cp -r ./static/. ${INVENIO_INSTANCE_PATH}/static/ && \
    cp -r ./assets/. ${INVENIO_INSTANCE_PATH}/assets/ && \
    invenio collect --verbose  && \
    invenio webpack buildall

ENTRYPOINT [ "bash", "-c"]
