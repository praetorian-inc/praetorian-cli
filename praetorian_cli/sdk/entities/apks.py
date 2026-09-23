import os


class Apks:
    """ The methods in this class are to be accessed from sdk.apks, where sdk is an instance
    of Chariot. """

    def __init__(self, api):
        self.api = api

    def add(self, local_filepath: str, chariot_filepath: str = None) -> dict:
        """
        Upload an Android APK and register it as an asset.

        This is two calls, because that is what Guard expects: the bytes go straight to
        storage with a presigned PUT, then POST /apk registers the stored object as an
        asset. No request carries the binary through the API.

        The package name is not a parameter. It is read server-side from the APK's
        AndroidManifest.xml, so the asset key is always '#apk#<package>' as declared by
        the binary itself, and a caller cannot register an arbitrary identity for an
        arbitrary file. Re-uploading a new build of the same app updates the existing
        asset rather than forking a second one.

        :param local_filepath: Path to the local .apk file to upload
        :type local_filepath: str
        :param chariot_filepath: Destination path in Guard storage. Defaults to the
            local file's base name.
        :type chariot_filepath: str or None
        :return: The registered APK asset, including its key, package and version
        :rtype: dict
        :raises Exception: If the file is missing, is not named .apk, or does not hold a
            readable Android manifest

        **Example Usage:**
            >>> apk = sdk.apks.add('./bank-app.apk')
            >>> print(apk['key'])
            #apk#com.bank.app
        """
        if not os.path.isfile(local_filepath):
            raise Exception(f'APK not found: {local_filepath}')

        if not chariot_filepath:
            chariot_filepath = os.path.basename(local_filepath)

        # POST /apk rejects an artifact_key that does not end in .apk, but only after
        # the upload has already happened. Checking here means a mis-named file costs
        # nothing instead of costing the whole transfer.
        if not chariot_filepath.lower().endswith('.apk'):
            raise Exception(f'the storage path must end in .apk, got "{chariot_filepath}"')

        self.api.upload(local_filepath, chariot_filepath)
        return self.api.post('apk', dict(artifact_key=chariot_filepath))
