# 3. Restricting permission set for communities

Date: 2024-02-25

## Status

Accepted

## Context

Permission set for handling the communities

## Decision

There is a defined set of roles that can handle the communities. The roles are:
- admin
- CONFIG_OEA_COMMUNITY_MANAGER_ROLE
- SystemProcess

## Consequences

This means that only the users with the above roles can handle the communities. Other users cannot create, update, or delete communities. This is a security measure to prevent unauthorized access to the communities. 
