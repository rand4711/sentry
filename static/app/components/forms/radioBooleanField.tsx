import {Fragment} from 'react';

import InputField from 'sentry/components/forms/inputField';
import {defined} from 'sentry/utils';

type Props = {
  noLabel: string;
  yesLabel: string;
  yesFirst?: boolean;
} & InputField['props'];

export default class RadioBooleanField extends InputField<Props> {
  static defaultProps = {
    ...InputField.defaultProps,
    yesLabel: 'Yes',
    noLabel: 'No',
    yesFirst: true,
  };

  coerceValue(props) {
    const value = super.coerceValue(props);
    return value ? true : false;
  }

  onChange = e => {
    const value = e.target.value === 'true';
    this.setValue(value);
  };

  getType() {
    return 'radio';
  }

  getField() {
    const yesOption = (
      <div className="radio" key="yes">
        <label style={{fontWeight: 'normal'}}>
          <input
            type="radio"
            value="true"
            name={this.props.name}
            checked={this.state.value === true}
            onChange={this.onChange.bind(this)}
            disabled={this.props.disabled}
          />{' '}
          {this.props.yesLabel}
        </label>
      </div>
    );
    const noOption = (
      <div className="radio" key="no">
        <label style={{fontWeight: 'normal'}}>
          <input
            type="radio"
            name={this.props.name}
            value="false"
            checked={this.state.value === false}
            onChange={this.onChange.bind(this)}
            disabled={this.props.disabled}
          />{' '}
          {this.props.noLabel}
        </label>
      </div>
    );
    return (
      <div className="control-group radio-boolean">
        {this.props.yesFirst ? (
          <Fragment>
            {yesOption}
            {noOption}
          </Fragment>
        ) : (
          <Fragment>
            {noOption}
            {yesOption}
          </Fragment>
        )}
      </div>
    );
  }

  render() {
    const {label, hideErrorMessage, help, style} = this.props;
    const {error} = this.state;
    const cx = this.getFinalClassNames();
    const shouldShowErrorMessage = error && !hideErrorMessage;

    return (
      <div style={style} className={cx}>
        <div className="controls">
          {label && (
            <label htmlFor={this.getId()} className="control-label">
              {label}
            </label>
          )}
          {defined(help) && <p className="help-block">{help}</p>}
          {this.getField()}
          {this.renderDisabledReason()}
          {shouldShowErrorMessage && <p className="error">{error}</p>}
        </div>
      </div>
    );
  }
}
