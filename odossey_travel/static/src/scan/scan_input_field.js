import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { scanBarcode } from "@web/core/barcode/barcode_dialog";
import { isBarcodeScannerSupported } from "@web/core/barcode/barcode_video_scanner";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component, onMounted, onWillUnmount, useRef } from "@odoo/owl";

/**
 * Input for identity documents: handheld 2D scanners in keyboard mode type the PDF417
 * content quickly and usually end with Enter. The value is committed after a short pause
 * or on Enter, so the server parses it immediately. The camera button uses the barcode
 * scanner of the web client (PDF417 and QR supported).
 */
export class TravelScanInputField extends Component {
    static template = "odossey_travel.TravelScanInputField";
    static props = { ...standardFieldProps };

    setup() {
        this.textareaRef = useRef("textarea");
        this.notification = useService("notification");
        this.cameraSupported = isBarcodeScannerSupported();
        this.timeout = null;
        onMounted(() => {
            if (!this.props.readonly) {
                this.textareaRef.el?.focus();
            }
        });
        onWillUnmount(() => clearTimeout(this.timeout));
    }

    get value() {
        return this.props.record.data[this.props.name] || "";
    }

    commit() {
        clearTimeout(this.timeout);
        const value = this.textareaRef.el.value;
        if (value !== this.value) {
            this.props.record.update({ [this.props.name]: value });
        }
    }

    onInput() {
        clearTimeout(this.timeout);
        this.timeout = setTimeout(() => this.commit(), 400);
    }

    onKeydown(ev) {
        // MRZ are pasted on several lines; a DNI scanner sends a single line + Enter
        if (ev.key === "Enter" && !ev.shiftKey && !this.textareaRef.el.value.includes("<")) {
            ev.preventDefault();
            this.commit();
        }
    }

    onClear() {
        this.textareaRef.el.value = "";
        this.commit();
        this.textareaRef.el.focus();
    }

    async onCamera() {
        let result;
        try {
            result = await scanBarcode(this.env);
        } catch (error) {
            this.notification.add(error?.message || _t("The camera could not be used."), {
                type: "danger",
            });
            return;
        }
        if (result) {
            this.textareaRef.el.value = result;
            this.commit();
        }
    }
}

registry.category("fields").add("travel_scan_input", {
    component: TravelScanInputField,
    supportedTypes: ["text"],
});
