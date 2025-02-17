import {Component} from 'react';

import {deviceNameMapper, loadDeviceListModule} from 'sentry/components/deviceName';
import TagDistributionMeter from 'sentry/components/tagDistributionMeter';
import {Group, Organization, TagWithTopValues} from 'sentry/types';
import {IOSDeviceList} from 'sentry/types/iOSDeviceList';

type Props = {
  group: Group;
  name: string;
  organization: Organization;
  projectId: string;
  tag: string;
  topValues: TagWithTopValues['topValues'];
  totalValues: number;
};

type State = {
  error: boolean;
  loading: boolean;
  iOSDeviceList?: IOSDeviceList;
};

class GroupTagDistributionMeter extends Component<Props, State> {
  state: State = {
    loading: true,
    error: false,
  };

  componentDidMount() {
    this.fetchData();
  }

  shouldComponentUpdate(nextProps: Props, nextState: State) {
    return (
      this.state.loading !== nextState.loading ||
      this.state.error !== nextState.error ||
      this.props.tag !== nextProps.tag ||
      this.props.name !== nextProps.name ||
      this.props.totalValues !== nextProps.totalValues ||
      this.props.topValues !== nextProps.topValues
    );
  }

  fetchData() {
    this.setState({
      loading: true,
      error: false,
    });

    loadDeviceListModule('iOS')
      .then(iOSDeviceList => {
        this.setState({
          iOSDeviceList,
          error: false,
          loading: false,
        });
      })
      .catch(() => {
        this.setState({
          error: true,
          loading: false,
        });
      });
  }

  render() {
    const {organization, group, tag, totalValues, topValues} = this.props;
    const {loading, error, iOSDeviceList} = this.state;

    const url = `/organizations/${organization.slug}/issues/${group.id}/tags/${tag}/`;

    const segments = topValues
      ? topValues.map(value => ({
          ...value,
          name: iOSDeviceList
            ? deviceNameMapper(value.name || '', iOSDeviceList) || ''
            : value.name,
          url,
        }))
      : [];

    return (
      <TagDistributionMeter
        title={tag}
        totalValues={totalValues}
        isLoading={loading}
        hasError={error}
        segments={segments}
      />
    );
  }
}

export default GroupTagDistributionMeter;
