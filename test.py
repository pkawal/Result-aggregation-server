import os,json
import unittest
from app import application, db
from app.models import UserSystemInfo, SuccessfulInstalls, FailedInstalls, Attempts

class TestCase(unittest.TestCase):
    def setUp(self):
        application.config['TESTING'] = True
        application.config['WTF_CSRF_ENABLED'] = False
        application.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/result_aggregation_test.db' 
        self.application = application.test_client()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_insertion(self):
    	u = UserSystemInfo(distribution_name="Ubuntu", distribution_version="15.10")
    	db.session.add(u)
    	db.session.commit()

    def test_post_data(self):
        data = {"user_system_info" : 
                    {"distribution_name": "Ubuntu", 
                        "distribution_version": "15.10",
                        "system_verson": "#42-Ubuntu SMP Thu May 12 22:05:35 UTC 2016",
                        "system": "Linux",
                        "machine": "x86_64",
                        "system_platform": "Linux-4.2.0-36-generic-x86_64-with-Ubuntu-15.10-wily",
                        "python_version" : "2.7.10"
                    },
                "failed_installs" : [{"name" : "EasyMercurial", "version": "2.5.0",
                                        "error_description": "errors finding EasyMercurial version"
                                     },
                                     {"name" : "Nose (nosetests)", "version": "4.0",
                                        "error_description": "errors finding Nose (nosetests) version"
                                     }
                                    ],
                "successful_installs": [{"name": "git", "version" : "2.5.0"},
                                        {"name": "make", "version" : "4.0"}
                                       ]
                }
        response = self.application.post('/installation_data/', data=json.dumps(data),
                                    headers={'Content-Type':'application/json'})
        self.assertEqual(response.status_code, 200)

if __name__ == '__main__':
    unittest.main()