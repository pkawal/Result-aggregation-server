from flask import Flask, jsonify, make_response
from app import application, db
from flask import request, render_template
from .models import UserSystemInfo, SuccessfulInstalls, FailedInstalls, Attempts
import uuid
from .limiter import *
from collections import Counter
import urllib.parse

@application.errorhandler(500)
def internal_error(error):
    db.session.rollback()

@application.route('/installation_data/', methods=['POST'])
@ratelimit(limit=500, per=60*60)
def installation_data():
    user_system_info = request.json.get('user_system_info')
    successful_installs = request.json.get('successful_installs')
    failed_installs = request.json.get('failed_installs')
    unique_user_id = request.json.get('unique_user_id')
    if unique_user_id is None:
        unique_user_id = str(uuid.uuid4())
        message = "new id generated"
        user_info = UserSystemInfo.query.filter_by(unique_user_id=unique_user_id).first()
        while(user_info): # Resolving Collision
            unique_user_id = str(uuid.uuid4())
            user_info = UserSystemInfo.query.filter_by(unique_user_id=unique_user_id).first()
    else:
        message = "pushed data with same id"
        """ Check whether the received unique id has already an associated record 
            in the database, or is it accidently changed by the user.
        """
        user_info = UserSystemInfo.query.filter_by(unique_user_id=unique_user_id).first()
        if user_info is None:
            unique_user_id = str(uuid.uuid4())
            message = "new id generated"

    distribution_name = user_system_info.get('distribution_name')
    distribution_version = user_system_info.get('distribution_version')
    system_version = user_system_info.get('system_version')
    system = user_system_info.get('system')
    machine = user_system_info.get('machine')
    system_platform = user_system_info.get('system_platform')
    python_version = user_system_info.get('python_version')
    workshop_id = user_system_info.get('workshop_id')
    email_id = user_system_info.get('email_id')
    # uname  = user_system_info.get('uname')

    attempt = Attempts(unique_user_id=unique_user_id)
   
    success_objects_list = [
        SuccessfulInstalls(name=succ_install.get('name'),version=succ_install.get('version')) 
            for succ_install in successful_installs 
    ]

    failed_objects_list = [
        FailedInstalls(name=fail_install.get('name'), version=fail_install.get('version'),
             error_description=fail_install.get('error_description')) 
            for fail_install in failed_installs
    ]
    
    user_info = UserSystemInfo.query.filter_by(unique_user_id=unique_user_id).first()
    if user_info is None:
        user_info = UserSystemInfo(distribution_name=distribution_name, 
                    distribution_version=distribution_version, system_version=system_version,
                    system=system, machine=machine, system_platform=system_platform,
                    workshop_id=workshop_id, email_id=email_id,
                    python_version=python_version, unique_user_id=unique_user_id)
    else: #Update anyway
        user_info.distribution_name = distribution_name
        user_info.distribution_version = distribution_version
        user_info.system_version = system_version
        user_info.system = system
        user_info.machine = machine
        user_info.system_platform = system_platform
        if email_id is not None:
            user_info.email_id = email_id
        if workshop_id is not None:
            user_info.workshop_id = workshop_id
        user_info.python_version = python_version
        user_info.unique_user_id = unique_user_id

    user_info.successful_installs.extend(success_objects_list)
    user_info.failed_installs.extend(failed_objects_list)
    attempt.successful_installs.extend(success_objects_list)
    attempt.failed_installs.extend(failed_objects_list)
    db.session.add(attempt)
    db.session.add(user_info)
    db.session.add_all(success_objects_list)
    db.session.add_all(failed_objects_list)
    
    try:
        db.session.commit()
    except:
        summary = {"status": "Something bad happened"}
    else:
        summary = {"status": "Successful"}
    summary['message'] = message
    response = {'key': unique_user_id, 'summary' : summary}
    return make_response(jsonify(response))

@application.route('/')
def default():
    return "<h1 style='color:blue'>Hello There!</h1>"


@application.route('/view/')
def data_view():
    user_info = db.session.query(UserSystemInfo.system, db.func.count().label("count")).group_by(UserSystemInfo.system).all()
    os_users = {}
    for user in user_info:
        os_users[user.system] = user.count

    failed_info = db.session.query(FailedInstalls.name, FailedInstalls.version, db.func.count().label("count")).group_by(FailedInstalls.name, FailedInstalls.version).all()
    most_failed_packages = [
        {"name": fail.name, "version": fail.version, "count" : fail.count}
        for fail in failed_info
    ]

    response = {"most_failed_packages": most_failed_packages, "os_users" : os_users}

    if request.args.get('export') == 'json':
        return make_response(jsonify(response))

    user_info = db.session.query(UserSystemInfo.workshop_id.distinct().label("workshop_id")).all()
    workshops = [
        user.workshop_id for user in user_info 
        if user.workshop_id is not None
    ]

    return render_template('index.html', response=response, workshops=workshops, show_all=True)


@application.route('/view/<workshop_id>/')
def data_view_by_workshop(workshop_id):
    user_info = db.session.query(UserSystemInfo.system, 
                    db.func.count().label("count")).filter_by(workshop_id=workshop_id
                    ).group_by(UserSystemInfo.system).all()
    os_users = {}
    for user in user_info:
        os_users[user.system] = user.count

    failed_info = FailedInstalls.query.join(UserSystemInfo,
                    UserSystemInfo.id==FailedInstalls.user_id).add_columns(
                    FailedInstalls.name, FailedInstalls.version, db.func.count().label("count")).filter(
                    UserSystemInfo.workshop_id==workshop_id).group_by(FailedInstalls.name, FailedInstalls.version)
    most_failed_packages = [
        {"name": fail.name, "version": fail.version, "count" : fail.count}
        for fail in failed_info
    ]

    response = {"most_failed_packages": most_failed_packages, "os_users" : os_users}

    if request.args.get('export') == 'json':
        return make_response(jsonify(response))

    user_info = db.session.query(UserSystemInfo.workshop_id.distinct().label("workshop_id")).all()
    workshops = [
        user.workshop_id for user in user_info 
        if user.workshop_id is not None
    ]

    return render_template('index.html', response=response, workshops=workshops, show_all=False)

@application.route('/view/detail/')
def data_view_detail_package():
    package_name = request.args.get('package_detail').split('|')[0]
    version = request.args.get('package_detail').split('|')[1]
    user_info = UserSystemInfo.query.join(FailedInstalls, 
                    UserSystemInfo.id==FailedInstalls.user_id).add_columns(
                    UserSystemInfo.distribution_name, UserSystemInfo.distribution_version,
                    UserSystemInfo.system, UserSystemInfo.system_platform,
                    UserSystemInfo.system_version, UserSystemInfo.machine,
                    UserSystemInfo.python_version).filter(
                    FailedInstalls.name==package_name, FailedInstalls.version==version)
    distribution_name = []; distribution_version = []; system = []; system_platform = [];
    system_version = []; machine = []; python_version = [];
    for user in user_info:
        distribution_name.append(user.distribution_name)
        distribution_version.append(user.distribution_version)
        system.append(user.system)
        system_platform.append(user.system_platform)
        system_version.append(user.system_version)
        machine.append(user.machine)
        python_version.append(user.python_version)

    distribution_name = filter(None,distribution_name)
    distribution_version = filter(None,distribution_version)
    system = filter(None,system)
    system_platform = filter(None,system_platform)
    system_version = filter(None,system_version)
    machine = filter(None,machine)
    python_version = filter(None,python_version)

    distribution_name = Counter(distribution_name)
    distribution_version = Counter(distribution_version)
    system = Counter(system)
    system_platform = Counter(system_platform)
    system_version = Counter(system_version)
    machine = Counter(machine)
    python_version = Counter(python_version)

    response = {
        "package_name" : package_name,
        "package_version" : version,
        "user_system_info" : {
            "distribution_name" : distribution_name, 
            "distribution_version" : distribution_version,
            "system" : system,
            "system_version" : system_version,
            "system_platform" : system_platform,
            "machine" : machine,
            "python_version" : python_version
        }
    }
    return make_response(jsonify(response))

@application.after_request
def inject_x_rate_headers(response):
    limit = get_view_rate_limit()
    if limit and limit.send_x_headers:
        h = response.headers
        h.add('X-RateLimit-Remaining', str(limit.remaining))
        h.add('X-RateLimit-Limit', str(limit.limit))
        h.add('X-RateLimit-Reset', str(limit.reset))
    return response
