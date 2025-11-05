class RedTeam:
    """
    Red Team operations entity for triggering terraform plan/apply and viewing history.
    """

    def __init__(self, api):
        self.api = api

    def plan(self) -> dict:
        """
        Trigger a terraform plan operation.

        Returns:
            dict: Response containing the plan operation status

        Example:
            >>> sdk.redteam.plan()
            {'message': 'Terraform plan triggered successfully', 'action': 'plan', 'status': 'initiated', ...}
        """
        return self.api.redteam_plan()

    def apply(self) -> dict:
        """
        Trigger a terraform apply operation.

        Returns:
            dict: Response containing the apply operation status

        Example:
            >>> sdk.redteam.apply()
            {'message': 'Terraform apply triggered successfully', 'action': 'apply', 'status': 'initiated', ...}
        """
        return self.api.redteam_apply()

    def launch(self, desired_id: str) -> dict:
        """
        Trigger a red team operation launch.

        Args:
            desired_id: Desired GCP project ID for the red team engagement. Backend will add random characters to make it unique.

        Returns:
            dict: Response containing the launch operation status

        Example:
            >>> sdk.redteam.launch('my-redteam-project')
            {'message': 'Red team launch triggered successfully', 'action': 'launch', 'status': 'initiated', ...}
        """
        return self.api.redteam_launch(desired_id)

    def history(self) -> list:
        """
        Retrieve historical red team operation records.

        Returns:
            list: List of historical operation records

        Example:
            >>> sdk.redteam.history()
            [{'id': 'op-001', 'action': 'plan', 'status': 'completed', ...}, ...]
        """
        return self.api.redteam_history()

    def update_collaborators(self, collaborators: list) -> dict:
        """
        Update collaborators for the current red team deployment.

        Args:
            collaborators: List of email addresses for collaborators who will have access to the red team project

        Returns:
            dict: Response containing the updated deployment information

        Example:
            >>> sdk.redteam.update_collaborators(['alice@praetorian.com', 'bob@praetorian.com'])
            {'message': 'Collaborators updated successfully', 'action': 'update_collaborators', 'status': 'completed', ...}
        """
        return self.api.redteam_update_collaborators(collaborators)

    def details(self) -> dict:
        """
        Retrieve the current red team deployment configuration.

        Returns:
            dict: Response containing the current deployment details including project_id, git_hash, principal, collaborators, and timestamps

        Example:
            >>> sdk.redteam.details()
            {'project_id': 'client-redteam-ab', 'git_hash': 'abc123...', 'principal': 'user@praetorian.com', 'collaborators': [...], ...}
        """
        return self.api.redteam_details()
