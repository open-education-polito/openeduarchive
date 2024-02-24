# 3. Mapping FARE metadata on top of DataCite

Date: 2024-02-24

## Status

Accepted

## Context

Metadata mapping

## Decision

We will map the FARE metadata on top of DataCite.
As such, we will use the DataCite schema as a base and extend it with the FARE metadata.

## Consequences

This means that:

* we keep the DataCite schema as a base, which is a well-known and widely used schema for research metadata.
* we extend the DataCite schema with the FARE metadata, which is a requirement for the FARE project.
* we keep the compatibility with both schemas.


In details:

* we will use the `subject` field as FARE's `argomento` field. This makes it possible to create an ad-hoc vocabulary containing the FARE's `argomento` values. 
* we will extend the DataCite schema with `disciplina` and `ordine di scuola` fields, which are specific to the FARE project. Those are controlled vocabularies and will be managed as such.
