import React from "react";
import { Checkbox } from "semantic-ui-react";
import { useFormikContext } from "formik";
import PropTypes from "prop-types";

const MetadataToggle = (props) => {
    const { filesEnabled } = props;
    const { setFieldValue } = useFormikContext();

    const handleOnChangeMetadataOnly = () => {
        setFieldValue("files.enabled", !filesEnabled);
        setFieldValue("access.files", "public");
    };

    return (
        <Checkbox
        toggle
        label="Metadata-only record"
        onChange={handleOnChangeMetadataOnly}
        />
    );
};

MetadataToggle.propTypes = {
    filesEnabled: PropTypes.bool.isRequired,
    };

export { MetadataToggle };