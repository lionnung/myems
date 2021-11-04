import falcon
import simplejson as json
import mysql.connector
import config
from datetime import datetime, timedelta, timezone
from core import utilities
from decimal import Decimal
import excelexporters.shopfloorstatistics


class Reporting:
    @staticmethod
    def __init__():
        """"Initializes Reporting"""
        pass

    @staticmethod
    def on_options(req, resp):
        resp.status = falcon.HTTP_200

    ####################################################################################################################
    # PROCEDURES
    # Step 1: valid parameters
    # Step 2: query the shopfloor
    # Step 3: query energy categories
    # Step 4: query associated sensors
    # Step 5: query associated points
    # Step 6: query base period energy input
    # Step 7: query reporting period energy input
    # Step 8: query tariff data
    # Step 9: query associated sensors and points data
    # Step 10: construct the report
    ####################################################################################################################
    @staticmethod
    def on_get(req, resp):
        print(req.params)
        shopfloor_id = req.params.get('shopfloorid')
        period_type = req.params.get('periodtype')
        base_start_datetime_local = req.params.get('baseperiodstartdatetime')
        base_end_datetime_local = req.params.get('baseperiodenddatetime')
        reporting_start_datetime_local = req.params.get('reportingperiodstartdatetime')
        reporting_end_datetime_local = req.params.get('reportingperiodenddatetime')

        ################################################################################################################
        # Step 1: valid parameters
        ################################################################################################################
        if shopfloor_id is None:
            raise falcon.HTTPError(falcon.HTTP_400, title='API.BAD_REQUEST', description='API.INVALID_SHOPFLOOR_ID')
        else:
            shopfloor_id = str.strip(shopfloor_id)
            if not shopfloor_id.isdigit() or int(shopfloor_id) <= 0:
                raise falcon.HTTPError(falcon.HTTP_400, title='API.BAD_REQUEST', description='API.INVALID_SHOPFLOOR_ID')

        if period_type is None:
            raise falcon.HTTPError(falcon.HTTP_400, title='API.BAD_REQUEST', description='API.INVALID_PERIOD_TYPE')
        else:
            period_type = str.strip(period_type)
            if period_type not in ['hourly', 'daily', 'weekly', 'monthly', 'yearly']:
                raise falcon.HTTPError(falcon.HTTP_400, title='API.BAD_REQUEST', description='API.INVALID_PERIOD_TYPE')

        timezone_offset = int(config.utc_offset[1:3]) * 60 + int(config.utc_offset[4:6])
        if config.utc_offset[0] == '-':
            timezone_offset = -timezone_offset

        base_start_datetime_utc = None
        if base_start_datetime_local is not None and len(str.strip(base_start_datetime_local)) > 0:
            base_start_datetime_local = str.strip(base_start_datetime_local)
            try:
                base_start_datetime_utc = datetime.strptime(base_start_datetime_local,
                                                            '%Y-%m-%dT%H:%M:%S').replace(tzinfo=timezone.utc) - \
                                          timedelta(minutes=timezone_offset)
            except ValueError:
                raise falcon.HTTPError(falcon.HTTP_400, title='API.BAD_REQUEST',
                                       description="API.INVALID_BASE_PERIOD_START_DATETIME")

        base_end_datetime_utc = None
        if base_end_datetime_local is not None and len(str.strip(base_end_datetime_local)) > 0:
            base_end_datetime_local = str.strip(base_end_datetime_local)
            try:
                base_end_datetime_utc = datetime.strptime(base_end_datetime_local,
                                                          '%Y-%m-%dT%H:%M:%S').replace(tzinfo=timezone.utc) - \
                                        timedelta(minutes=timezone_offset)
            except ValueError:
                raise falcon.HTTPError(falcon.HTTP_400, title='API.BAD_REQUEST',
                                       description="API.INVALID_BASE_PERIOD_END_DATETIME")

        if base_start_datetime_utc is not None and base_end_datetime_utc is not None and \
                base_start_datetime_utc >= base_end_datetime_utc:
            raise falcon.HTTPError(falcon.HTTP_400, title='API.BAD_REQUEST',
                                   description='API.INVALID_BASE_PERIOD_END_DATETIME')

        if reporting_start_datetime_local is None:
            raise falcon.HTTPError(falcon.HTTP_400, title='API.BAD_REQUEST',
                                   description="API.INVALID_REPORTING_PERIOD_START_DATETIME")
        else:
            reporting_start_datetime_local = str.strip(reporting_start_datetime_local)
            try:
                reporting_start_datetime_utc = datetime.strptime(reporting_start_datetime_local,
                                                                 '%Y-%m-%dT%H:%M:%S').replace(tzinfo=timezone.utc) - \
                                               timedelta(minutes=timezone_offset)
            except ValueError:
                raise falcon.HTTPError(falcon.HTTP_400, title='API.BAD_REQUEST',
                                       description="API.INVALID_REPORTING_PERIOD_START_DATETIME")

        if reporting_end_datetime_local is None:
            raise falcon.HTTPError(falcon.HTTP_400, title='API.BAD_REQUEST',
                                   description="API.INVALID_REPORTING_PERIOD_END_DATETIME")
        else:
            reporting_end_datetime_local = str.strip(reporting_end_datetime_local)
            try:
                reporting_end_datetime_utc = datetime.strptime(reporting_end_datetime_local,
                                                               '%Y-%m-%dT%H:%M:%S').replace(tzinfo=timezone.utc) - \
                                             timedelta(minutes=timezone_offset)
            except ValueError:
                raise falcon.HTTPError(falcon.HTTP_400, title='API.BAD_REQUEST',
                                       description="API.INVALID_REPORTING_PERIOD_END_DATETIME")

        if reporting_start_datetime_utc >= reporting_end_datetime_utc:
            raise falcon.HTTPError(falcon.HTTP_400, title='API.BAD_REQUEST',
                                   description='API.INVALID_REPORTING_PERIOD_END_DATETIME')

        ################################################################################################################
        # Step 2: query the shopfloor
        ################################################################################################################
        cnx_system = mysql.connector.connect(**config.myems_system_db)
        cursor_system = cnx_system.cursor()

        cnx_energy = mysql.connector.connect(**config.myems_energy_db)
        cursor_energy = cnx_energy.cursor()

        cnx_historical = mysql.connector.connect(**config.myems_historical_db)
        cursor_historical = cnx_historical.cursor()

        cursor_system.execute(" SELECT id, name, area, cost_center_id "
                              " FROM tbl_shopfloors "
                              " WHERE id = %s ", (shopfloor_id,))
        row_shopfloor = cursor_system.fetchone()
        if row_shopfloor is None:
            if cursor_system:
                cursor_system.close()
            if cnx_system:
                cnx_system.disconnect()

            if cursor_energy:
                cursor_energy.close()
            if cnx_energy:
                cnx_energy.disconnect()

            if cursor_historical:
                cursor_historical.close()
            if cnx_historical:
                cnx_historical.disconnect()
            raise falcon.HTTPError(falcon.HTTP_404, title='API.NOT_FOUND', description='API.SHOPFLOOR_NOT_FOUND')

        shopfloor = dict()
        shopfloor['id'] = row_shopfloor[0]
        shopfloor['name'] = row_shopfloor[1]
        shopfloor['area'] = row_shopfloor[2]
        shopfloor['cost_center_id'] = row_shopfloor[3]

        ################################################################################################################
        # Step 3: query energy categories
        ################################################################################################################
        energy_category_set = set()
        # query energy categories in base period
        cursor_energy.execute(" SELECT DISTINCT(energy_category_id) "
                              " FROM tbl_shopfloor_input_category_hourly "
                              " WHERE shopfloor_id = %s "
                              "     AND start_datetime_utc >= %s "
                              "     AND start_datetime_utc < %s ",
                              (shopfloor['id'], base_start_datetime_utc, base_end_datetime_utc))
        rows_energy_categories = cursor_energy.fetchall()
        if rows_energy_categories is not None or len(rows_energy_categories) > 0:
            for row_energy_category in rows_energy_categories:
                energy_category_set.add(row_energy_category[0])

        # query energy categories in reporting period
        cursor_energy.execute(" SELECT DISTINCT(energy_category_id) "
                              " FROM tbl_shopfloor_input_category_hourly "
                              " WHERE shopfloor_id = %s "
                              "     AND start_datetime_utc >= %s "
                              "     AND start_datetime_utc < %s ",
                              (shopfloor['id'], reporting_start_datetime_utc, reporting_end_datetime_utc))
        rows_energy_categories = cursor_energy.fetchall()
        if rows_energy_categories is not None or len(rows_energy_categories) > 0:
            for row_energy_category in rows_energy_categories:
                energy_category_set.add(row_energy_category[0])

        # query all energy categories in base period and reporting period
        cursor_system.execute(" SELECT id, name, unit_of_measure, kgce, kgco2e "
                              " FROM tbl_energy_categories "
                              " ORDER BY id ", )
        rows_energy_categories = cursor_system.fetchall()
        if rows_energy_categories is None or len(rows_energy_categories) == 0:
            if cursor_system:
                cursor_system.close()
            if cnx_system:
                cnx_system.disconnect()

            if cursor_energy:
                cursor_energy.close()
            if cnx_energy:
                cnx_energy.disconnect()

            if cursor_historical:
                cursor_historical.close()
            if cnx_historical:
                cnx_historical.disconnect()
            raise falcon.HTTPError(falcon.HTTP_404,
                                   title='API.NOT_FOUND',
                                   description='API.ENERGY_CATEGORY_NOT_FOUND')
        energy_category_dict = dict()
        for row_energy_category in rows_energy_categories:
            if row_energy_category[0] in energy_category_set:
                energy_category_dict[row_energy_category[0]] = {"name": row_energy_category[1],
                                                                "unit_of_measure": row_energy_category[2],
                                                                "kgce": row_energy_category[3],
                                                                "kgco2e": row_energy_category[4]}

        ################################################################################################################
        # Step 4: query associated sensors
        ################################################################################################################
        point_list = list()
        cursor_system.execute(" SELECT p.id, p.name, p.units, p.object_type  "
                              " FROM tbl_shopfloors st, tbl_sensors se, tbl_shopfloors_sensors ss, "
                              "      tbl_points p, tbl_sensors_points sp "
                              " WHERE st.id = %s AND st.id = ss.shopfloor_id AND ss.sensor_id = se.id "
                              "       AND se.id = sp.sensor_id AND sp.point_id = p.id "
                              " ORDER BY p.id ", (shopfloor['id'],))
        rows_points = cursor_system.fetchall()
        if rows_points is not None and len(rows_points) > 0:
            for row in rows_points:
                point_list.append({"id": row[0], "name": row[1], "units": row[2], "object_type": row[3]})

        ################################################################################################################
        # Step 5: query associated points
        ################################################################################################################
        cursor_system.execute(" SELECT p.id, p.name, p.units, p.object_type  "
                              " FROM tbl_shopfloors s, tbl_shopfloors_points sp, tbl_points p "
                              " WHERE s.id = %s AND s.id = sp.shopfloor_id AND sp.point_id = p.id "
                              " ORDER BY p.id ", (shopfloor['id'],))
        rows_points = cursor_system.fetchall()
        if rows_points is not None and len(rows_points) > 0:
            for row in rows_points:
                point_list.append({"id": row[0], "name": row[1], "units": row[2], "object_type": row[3]})

        ################################################################################################################
        # Step 6: query base period energy input
        ################################################################################################################
        base = dict()
        if energy_category_set is not None and len(energy_category_set) > 0:
            for energy_category_id in energy_category_set:
                base[energy_category_id] = dict()
                base[energy_category_id]['timestamps'] = list()
                base[energy_category_id]['values'] = list()
                base[energy_category_id]['subtotal'] = Decimal(0.0)
                base[energy_category_id]['mean'] = None
                base[energy_category_id]['median'] = None
                base[energy_category_id]['minimum'] = None
                base[energy_category_id]['maximum'] = None
                base[energy_category_id]['stdev'] = None
                base[energy_category_id]['variance'] = None

                cursor_energy.execute(" SELECT start_datetime_utc, actual_value "
                                      " FROM tbl_shopfloor_input_category_hourly "
                                      " WHERE shopfloor_id = %s "
                                      "     AND energy_category_id = %s "
                                      "     AND start_datetime_utc >= %s "
                                      "     AND start_datetime_utc < %s "
                                      " ORDER BY start_datetime_utc ",
                                      (shopfloor['id'],
                                       energy_category_id,
                                       base_start_datetime_utc,
                                       base_end_datetime_utc))
                rows_shopfloor_hourly = cursor_energy.fetchall()

                rows_shopfloor_periodically, \
                    base[energy_category_id]['mean'], \
                    base[energy_category_id]['median'], \
                    base[energy_category_id]['minimum'], \
                    base[energy_category_id]['maximum'], \
                    base[energy_category_id]['stdev'], \
                    base[energy_category_id]['variance'] = \
                    utilities.statistics_hourly_data_by_period(rows_shopfloor_hourly,
                                                               base_start_datetime_utc,
                                                               base_end_datetime_utc,
                                                               period_type)

                for row_shopfloor_periodically in rows_shopfloor_periodically:
                    current_datetime_local = row_shopfloor_periodically[0].replace(tzinfo=timezone.utc) + \
                                             timedelta(minutes=timezone_offset)
                    if period_type == 'hourly':
                        current_datetime = current_datetime_local.strftime('%Y-%m-%dT%H:%M:%S')
                    elif period_type == 'daily':
                        current_datetime = current_datetime_local.strftime('%Y-%m-%d')
                    elif period_type == 'weekly':
                        current_datetime = current_datetime_local.strftime('%Y-%m-%d')
                    elif period_type == 'monthly':
                        current_datetime = current_datetime_local.strftime('%Y-%m')
                    elif period_type == 'yearly':
                        current_datetime = current_datetime_local.strftime('%Y')

                    actual_value = Decimal(0.0) if row_shopfloor_periodically[1] is None \
                        else row_shopfloor_periodically[1]
                    base[energy_category_id]['timestamps'].append(current_datetime)
                    base[energy_category_id]['values'].append(actual_value)
                    base[energy_category_id]['subtotal'] += actual_value

        ################################################################################################################
        # Step 7: query reporting period energy input
        ################################################################################################################
        reporting = dict()
        if energy_category_set is not None and len(energy_category_set) > 0:
            for energy_category_id in energy_category_set:
                reporting[energy_category_id] = dict()
                reporting[energy_category_id]['timestamps'] = list()
                reporting[energy_category_id]['values'] = list()
                reporting[energy_category_id]['subtotal'] = Decimal(0.0)
                reporting[energy_category_id]['mean'] = None
                reporting[energy_category_id]['median'] = None
                reporting[energy_category_id]['minimum'] = None
                reporting[energy_category_id]['maximum'] = None
                reporting[energy_category_id]['stdev'] = None
                reporting[energy_category_id]['variance'] = None

                cursor_energy.execute(" SELECT start_datetime_utc, actual_value "
                                      " FROM tbl_shopfloor_input_category_hourly "
                                      " WHERE shopfloor_id = %s "
                                      "     AND energy_category_id = %s "
                                      "     AND start_datetime_utc >= %s "
                                      "     AND start_datetime_utc < %s "
                                      " ORDER BY start_datetime_utc ",
                                      (shopfloor['id'],
                                       energy_category_id,
                                       reporting_start_datetime_utc,
                                       reporting_end_datetime_utc))
                rows_shopfloor_hourly = cursor_energy.fetchall()

                rows_shopfloor_periodically, \
                    reporting[energy_category_id]['mean'], \
                    reporting[energy_category_id]['median'], \
                    reporting[energy_category_id]['minimum'], \
                    reporting[energy_category_id]['maximum'], \
                    reporting[energy_category_id]['stdev'], \
                    reporting[energy_category_id]['variance'] = \
                    utilities.statistics_hourly_data_by_period(rows_shopfloor_hourly,
                                                               reporting_start_datetime_utc,
                                                               reporting_end_datetime_utc,
                                                               period_type)

                for row_shopfloor_periodically in rows_shopfloor_periodically:
                    current_datetime_local = row_shopfloor_periodically[0].replace(tzinfo=timezone.utc) + \
                                             timedelta(minutes=timezone_offset)
                    if period_type == 'hourly':
                        current_datetime = current_datetime_local.strftime('%Y-%m-%dT%H:%M:%S')
                    elif period_type == 'daily':
                        current_datetime = current_datetime_local.strftime('%Y-%m-%d')
                    elif period_type == 'weekly':
                        current_datetime = current_datetime_local.strftime('%Y-%m-%d')
                    elif period_type == 'monthly':
                        current_datetime = current_datetime_local.strftime('%Y-%m')
                    elif period_type == 'yearly':
                        current_datetime = current_datetime_local.strftime('%Y')

                    actual_value = Decimal(0.0) if row_shopfloor_periodically[1] is None \
                        else row_shopfloor_periodically[1]
                    reporting[energy_category_id]['timestamps'].append(current_datetime)
                    reporting[energy_category_id]['values'].append(actual_value)
                    reporting[energy_category_id]['subtotal'] += actual_value

        ################################################################################################################
        # Step 8: query tariff data
        ################################################################################################################
        parameters_data = dict()
        parameters_data['names'] = list()
        parameters_data['timestamps'] = list()
        parameters_data['values'] = list()
        if energy_category_set is not None and len(energy_category_set) > 0:
            for energy_category_id in energy_category_set:
                energy_category_tariff_dict = utilities.get_energy_category_tariffs(shopfloor['cost_center_id'],
                                                                                    energy_category_id,
                                                                                    reporting_start_datetime_utc,
                                                                                    reporting_end_datetime_utc)
                tariff_timestamp_list = list()
                tariff_value_list = list()
                for k, v in energy_category_tariff_dict.items():
                    # convert k from utc to local
                    k = k + timedelta(minutes=timezone_offset)
                    tariff_timestamp_list.append(k.isoformat()[0:19][0:19])
                    tariff_value_list.append(v)

                parameters_data['names'].append('TARIFF-' + energy_category_dict[energy_category_id]['name'])
                parameters_data['timestamps'].append(tariff_timestamp_list)
                parameters_data['values'].append(tariff_value_list)

        ################################################################################################################
        # Step 9: query associated sensors and points data
        ################################################################################################################
        for point in point_list:
            point_values = []
            point_timestamps = []
            if point['object_type'] == 'ANALOG_VALUE':
                query = (" SELECT utc_date_time, actual_value "
                         " FROM tbl_analog_value "
                         " WHERE point_id = %s "
                         "       AND utc_date_time BETWEEN %s AND %s "
                         " ORDER BY utc_date_time ")
                cursor_historical.execute(query, (point['id'],
                                                  reporting_start_datetime_utc,
                                                  reporting_end_datetime_utc))
                rows = cursor_historical.fetchall()

                if rows is not None and len(rows) > 0:
                    for row in rows:
                        current_datetime_local = row[0].replace(tzinfo=timezone.utc) + \
                                                 timedelta(minutes=timezone_offset)
                        current_datetime = current_datetime_local.strftime('%Y-%m-%dT%H:%M:%S')
                        point_timestamps.append(current_datetime)
                        point_values.append(row[1])

            elif point['object_type'] == 'ENERGY_VALUE':
                query = (" SELECT utc_date_time, actual_value "
                         " FROM tbl_energy_value "
                         " WHERE point_id = %s "
                         "       AND utc_date_time BETWEEN %s AND %s "
                         " ORDER BY utc_date_time ")
                cursor_historical.execute(query, (point['id'],
                                                  reporting_start_datetime_utc,
                                                  reporting_end_datetime_utc))
                rows = cursor_historical.fetchall()

                if rows is not None and len(rows) > 0:
                    for row in rows:
                        current_datetime_local = row[0].replace(tzinfo=timezone.utc) + \
                                                 timedelta(minutes=timezone_offset)
                        current_datetime = current_datetime_local.strftime('%Y-%m-%dT%H:%M:%S')
                        point_timestamps.append(current_datetime)
                        point_values.append(row[1])
            elif point['object_type'] == 'DIGITAL_VALUE':
                query = (" SELECT utc_date_time, actual_value "
                         " FROM tbl_digital_value "
                         " WHERE point_id = %s "
                         "       AND utc_date_time BETWEEN %s AND %s "
                         " ORDER BY utc_date_time ")
                cursor_historical.execute(query, (point['id'],
                                                  reporting_start_datetime_utc,
                                                  reporting_end_datetime_utc))
                rows = cursor_historical.fetchall()

                if rows is not None and len(rows) > 0:
                    for row in rows:
                        current_datetime_local = row[0].replace(tzinfo=timezone.utc) + \
                                                 timedelta(minutes=timezone_offset)
                        current_datetime = current_datetime_local.strftime('%Y-%m-%dT%H:%M:%S')
                        point_timestamps.append(current_datetime)
                        point_values.append(row[1])

            parameters_data['names'].append(point['name'] + ' (' + point['units'] + ')')
            parameters_data['timestamps'].append(point_timestamps)
            parameters_data['values'].append(point_values)

        ################################################################################################################
        # Step 10: construct the report
        ################################################################################################################
        if cursor_system:
            cursor_system.close()
        if cnx_system:
            cnx_system.disconnect()

        if cursor_energy:
            cursor_energy.close()
        if cnx_energy:
            cnx_energy.disconnect()

        if cursor_historical:
            cursor_historical.close()
        if cnx_historical:
            cnx_historical.disconnect()

        result = dict()

        result['shopfloor'] = dict()
        result['shopfloor']['name'] = shopfloor['name']
        result['shopfloor']['area'] = shopfloor['area']

        result['base_period'] = dict()
        result['base_period']['names'] = list()
        result['base_period']['units'] = list()
        result['base_period']['timestamps'] = list()
        result['base_period']['values'] = list()
        result['base_period']['subtotals'] = list()
        result['base_period']['means'] = list()
        result['base_period']['medians'] = list()
        result['base_period']['minimums'] = list()
        result['base_period']['maximums'] = list()
        result['base_period']['stdevs'] = list()
        result['base_period']['variances'] = list()

        if energy_category_set is not None and len(energy_category_set) > 0:
            for energy_category_id in energy_category_set:
                result['base_period']['names'].append(energy_category_dict[energy_category_id]['name'])
                result['base_period']['units'].append(energy_category_dict[energy_category_id]['unit_of_measure'])
                result['base_period']['timestamps'].append(base[energy_category_id]['timestamps'])
                result['base_period']['values'].append(base[energy_category_id]['values'])
                result['base_period']['subtotals'].append(base[energy_category_id]['subtotal'])
                result['base_period']['means'].append(base[energy_category_id]['mean'])
                result['base_period']['medians'].append(base[energy_category_id]['median'])
                result['base_period']['minimums'].append(base[energy_category_id]['minimum'])
                result['base_period']['maximums'].append(base[energy_category_id]['maximum'])
                result['base_period']['stdevs'].append(base[energy_category_id]['stdev'])
                result['base_period']['variances'].append(base[energy_category_id]['variance'])

        result['reporting_period'] = dict()
        result['reporting_period']['names'] = list()
        result['reporting_period']['energy_category_ids'] = list()
        result['reporting_period']['units'] = list()
        result['reporting_period']['timestamps'] = list()
        result['reporting_period']['values'] = list()
        result['reporting_period']['subtotals'] = list()
        result['reporting_period']['means'] = list()
        result['reporting_period']['means_per_unit_area'] = list()
        result['reporting_period']['means_increment_rate'] = list()
        result['reporting_period']['medians'] = list()
        result['reporting_period']['medians_per_unit_area'] = list()
        result['reporting_period']['medians_increment_rate'] = list()
        result['reporting_period']['minimums'] = list()
        result['reporting_period']['minimums_per_unit_area'] = list()
        result['reporting_period']['minimums_increment_rate'] = list()
        result['reporting_period']['maximums'] = list()
        result['reporting_period']['maximums_per_unit_area'] = list()
        result['reporting_period']['maximums_increment_rate'] = list()
        result['reporting_period']['stdevs'] = list()
        result['reporting_period']['stdevs_per_unit_area'] = list()
        result['reporting_period']['stdevs_increment_rate'] = list()
        result['reporting_period']['variances'] = list()
        result['reporting_period']['variances_per_unit_area'] = list()
        result['reporting_period']['variances_increment_rate'] = list()

        if energy_category_set is not None and len(energy_category_set) > 0:
            for energy_category_id in energy_category_set:
                result['reporting_period']['names'].append(energy_category_dict[energy_category_id]['name'])
                result['reporting_period']['energy_category_ids'].append(energy_category_id)
                result['reporting_period']['units'].append(energy_category_dict[energy_category_id]['unit_of_measure'])
                result['reporting_period']['timestamps'].append(reporting[energy_category_id]['timestamps'])
                result['reporting_period']['values'].append(reporting[energy_category_id]['values'])
                result['reporting_period']['subtotals'].append(reporting[energy_category_id]['subtotal'])
                result['reporting_period']['means'].append(reporting[energy_category_id]['mean'])
                result['reporting_period']['means_per_unit_area'].append(
                    reporting[energy_category_id]['mean'] / shopfloor['area']
                    if reporting[energy_category_id]['mean'] is not None and
                    shopfloor['area'] is not None and
                    shopfloor['area'] > Decimal(0.0)
                    else None)
                result['reporting_period']['means_increment_rate'].append(
                    (reporting[energy_category_id]['mean'] - base[energy_category_id]['mean']) /
                    base[energy_category_id]['mean'] if (base[energy_category_id]['mean'] is not None and
                                                         base[energy_category_id]['mean'] > Decimal(0.0))
                    else None)
                result['reporting_period']['medians'].append(reporting[energy_category_id]['median'])
                result['reporting_period']['medians_per_unit_area'].append(
                    reporting[energy_category_id]['median'] / shopfloor['area']
                    if reporting[energy_category_id]['median'] is not None and
                    shopfloor['area'] is not None and
                    shopfloor['area'] > Decimal(0.0)
                    else None)
                result['reporting_period']['medians_increment_rate'].append(
                    (reporting[energy_category_id]['median'] - base[energy_category_id]['median']) /
                    base[energy_category_id]['median'] if (base[energy_category_id]['median'] is not None and
                                                           base[energy_category_id]['median'] > Decimal(0.0))
                    else None)
                result['reporting_period']['minimums'].append(reporting[energy_category_id]['minimum'])
                result['reporting_period']['minimums_per_unit_area'].append(
                    reporting[energy_category_id]['minimum'] / shopfloor['area']
                    if reporting[energy_category_id]['minimum'] is not None and
                    shopfloor['area'] is not None and
                    shopfloor['area'] > Decimal(0.0)
                    else None)
                result['reporting_period']['minimums_increment_rate'].append(
                    (reporting[energy_category_id]['minimum'] - base[energy_category_id]['minimum']) /
                    base[energy_category_id]['minimum'] if (base[energy_category_id]['minimum'] is not None and
                                                            base[energy_category_id]['minimum'] > Decimal(0.0))
                    else None)
                result['reporting_period']['maximums'].append(reporting[energy_category_id]['maximum'])
                result['reporting_period']['maximums_per_unit_area'].append(
                    reporting[energy_category_id]['maximum'] / shopfloor['area']
                    if reporting[energy_category_id]['maximum'] is not None and
                    shopfloor['area'] is not None and
                    shopfloor['area'] > Decimal(0.0)
                    else None)
                result['reporting_period']['maximums_increment_rate'].append(
                    (reporting[energy_category_id]['maximum'] - base[energy_category_id]['maximum']) /
                    base[energy_category_id]['maximum'] if (base[energy_category_id]['maximum'] is not None and
                                                            base[energy_category_id]['maximum'] > Decimal(0.0))
                    else None)
                result['reporting_period']['stdevs'].append(reporting[energy_category_id]['stdev'])
                result['reporting_period']['stdevs_per_unit_area'].append(
                    reporting[energy_category_id]['stdev'] / shopfloor['area']
                    if reporting[energy_category_id]['stdev'] is not None and
                    shopfloor['area'] is not None and
                    shopfloor['area'] > Decimal(0.0)
                    else None)
                result['reporting_period']['stdevs_increment_rate'].append(
                    (reporting[energy_category_id]['stdev'] - base[energy_category_id]['stdev']) /
                    base[energy_category_id]['stdev'] if (base[energy_category_id]['stdev'] is not None and
                                                          base[energy_category_id]['stdev'] > Decimal(0.0))
                    else None)
                result['reporting_period']['variances'].append(reporting[energy_category_id]['variance'])
                result['reporting_period']['variances_per_unit_area'].append(
                    reporting[energy_category_id]['variance'] / shopfloor['area']
                    if reporting[energy_category_id]['variance'] is not None and
                    shopfloor['area'] is not None and
                    shopfloor['area'] > Decimal(0.0)
                    else None)
                result['reporting_period']['variances_increment_rate'].append(
                    (reporting[energy_category_id]['variance'] - base[energy_category_id]['variance']) /
                    base[energy_category_id]['variance'] if (base[energy_category_id]['variance'] is not None and
                                                             base[energy_category_id]['variance'] > Decimal(0.0))
                    else None)

        result['parameters'] = {
            "names": parameters_data['names'],
            "timestamps": parameters_data['timestamps'],
            "values": parameters_data['values']
        }

        # export result to Excel file and then encode the file to base64 string
        result['excel_bytes_base64'] = excelexporters.shopfloorstatistics.export(result,
                                                                                 shopfloor['name'],
                                                                                 reporting_start_datetime_local,
                                                                                 reporting_end_datetime_local,
                                                                                 period_type)

        resp.body = json.dumps(result)
