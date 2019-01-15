PERMISSIONS_FUNCTION_PACKAGE_JSON = """
{
  "dependencies": {
    "@google-cloud/storage": "^2.3.4"
  }
}
"""


PERMISSIONS_FUNCTION_JS = lambda function_name, project_id, bucket_name: """
exports.""" + function_name + """ = (event, callback) => {
  const {Storage} = require('@google-cloud/storage');
  const projectId = '""" + project_id + """';
  const bucketName = '"""+ bucket_name +"""';
  const file_name = event.data.name;
  if (file_name === 'ckan') {
      callback();
  } else {
      console.log(`  File: ${file_name}`);
      const storage = new Storage();
      const bucket = storage.bucket(bucketName);
      const file = bucket.file(file_name)
      file.makePrivate().then(function(){
        callback();
      }).catch(function(err){
        callback(err);
      });
  };
};
"""
