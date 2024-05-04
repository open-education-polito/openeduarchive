# Commands

This file contains a set of vital commands to handle the OEA instance correctly.


## User management

`invenio roles add <email> admin`

`invenio users create <email> --password <pwd> --active --confirm`



## Launch

invenio-cli run
invenio-cli services setup -N -f
invenio-cli services start
invenio-cli services destroy

After change in a JS / CSS file:
`invenio-cli assets build`

Adding custom fields:
`invenio rdm-records custom-fields init -f oea:educationLevel`

Adding vocabularies:
`invenio vocabularies import -f app_data/vocabularies/oea_education_level.yaml`