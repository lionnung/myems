import React, { useState, useContext } from 'react';
import { Row, Col, Card, CardBody } from 'reactstrap';
import { CheckPicker } from 'rsuite';
import { Line } from 'react-chartjs-2';
import { rgbaColor, themeColors, isIterableArray } from '../../../helpers/utils';
import AppContext from '../../../context/Context';

const MultipleLineChart = ({
  reportingTitle,
  baseTitle,
  labels,
  data,
  options
}) => {
  const [values, setValues] = useState(['a0']);
  const { isDark } = useContext(AppContext);
  const [nodes, setNodes] = useState([{value: 'a0', label: options.label}])

  let handleChange = (arr) => {
    setValues(arr);
    let nodes = [];
    arr.forEach(item => {
      let index = item.slice(1);
      nodes.push({value: item, label: options[index].label})
    });
    setNodes(nodes);
  }

  const config = {
    data(canvas) {
      const ctx = canvas.getContext('2d');
      const gradientFill = isDark
        ? ctx.createLinearGradient(0, 0, 0, ctx.canvas.height)
        : ctx.createLinearGradient(0, 0, 0, 250);
      gradientFill.addColorStop(0, isDark ? 'rgba(44,123,229, 0.5)' : 'rgba(255, 255, 255, 0.3)');
      gradientFill.addColorStop(1, isDark ? 'transparent' : 'rgba(255, 255, 255, 0)');
      let sets = [];
      nodes.forEach(item => {
        sets.push({
          label: item.label,
          borderWidth: 2,
          data: data[item.value],
          borderColor: rgbaColor(isDark ? themeColors.primary : '#000', 0.8),
          backgroundColor: gradientFill
        })
      })
      return {
        labels: labels[values[0]],
        datasets: sets
      };
    },
    options: {
      legend: { display: false },
      tooltips: {
        mode: 'x-axis',
        xPadding: 20,
        yPadding: 10,
        displayColors: false,
      },
      hover: { mode: 'label' },
      scales: {
        xAxes: [
          {
            ticks: {
              fontColor: rgbaColor('#789', 0.8),
              fontStyle: 600
            },
            gridLines: {
              color: rgbaColor('#000', 0.1),
              zeroLineColor: rgbaColor('#000', 0.1),
              lineWidth: 1
            }
          }
        ],
        yAxes: [
          {
            display: true,
            gridLines: {
              color: rgbaColor('#000', 0.1)
            }
          }
        ]
      }
    }
  };
  return (
    <Card className="mb-3">
      <CardBody className="rounded-soft">
        <Row className="text-white align-items-center no-gutters">
          <Col>
            <h4 className="text-lightSlateGray mb-0">{reportingTitle}</h4>
            <p className="fs--1 font-weight-semi-bold">
              {baseTitle}
            </p>
          </Col>
          {isIterableArray(options) &&
            <Col xs="auto" className="d-none d-sm-block">
              <CheckPicker
                data={options}
                value={values}
                appearance="default"
                placeholder="select"
                searchable={false}
                countable={false}
                onSelect={handleChange}
                style={{ width: 224, borderRadius: '.25rem'}}
                />
            </Col>
          }
        </Row>
        <Line data={config.data} options={config.options} width={1618} height={375} />
      </CardBody>
    </Card>
  );
};

export default MultipleLineChart;
