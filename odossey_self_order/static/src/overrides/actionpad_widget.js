// No JS overrides needed.
// The submit-order button state is fully controlled by last_order_preparation_change,
// which the Python controller sets when self-order lines are sent to the KDS.
// When all lines are recorded there, categoryCount === 0 and the button is already
// disabled (btn-light pe-none disabled) by the standard pos_restaurant logic.
