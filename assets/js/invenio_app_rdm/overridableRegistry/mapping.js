// This file is part of InvenioRDM
// Copyright (C) 2023 CERN.
//
// Invenio App RDM is free software; you can redistribute it and/or modify it
// under the terms of the MIT License; see LICENSE file for more details.

/**
 * Add here all the overridden components of your app.
 */

import { MetadataToggle } from "../../components/deposit_ui/overrides/MetadataToggle";

export const overriddenComponents = {
    "ReactInvenioDeposit.FileUploaderToolbar.MetadataOnlyToggle.container": MetadataToggle,
    "InvenioAppRdm.Deposit.AccordionFieldFunding.container": () => null,
    "InvenioAppRdm.Deposit.AccordionFieldReferences.container": () => null,
    "InvenioAppRdm.Deposit.AccordionFieldAlternateIdentifiers.container": () => null,
    "InvenioAppRdm.Deposit.AccordionFieldRelatedWorks.container": () => null,
    "InvenioAppRdm.Deposit.AccordionFieldRecommendedInformation.container": () => null,
};