package test

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	awsSDK "github.com/aws/aws-sdk-go/aws"
	"github.com/aws/aws-sdk-go/aws/session"
	"github.com/aws/aws-sdk-go/service/s3"
	"github.com/gruntwork-io/terratest/modules/random"
	terraform "github.com/gruntwork-io/terratest/modules/terraform"
	"github.com/stretchr/testify/require"
)

const (
	stagingConfirmation = "YES-STAGING-ONLY"
	terraformDirectory  = ".."
)

func requireStaging(t *testing.T, mode string) {
	t.Helper()
	require.Equal(t, "staging", os.Getenv("SYNTH_NOW_TERRATEST_ENVIRONMENT"), "Terratest only runs against an explicitly named staging environment")
	require.NotEmpty(t, os.Getenv("SYNTH_NOW_TERRATEST_APPROVED_ACCOUNT_ID"), "set the approved isolated staging AWS account ID")
	if mode == "apply" {
		require.Equal(t, stagingConfirmation, os.Getenv("SYNTH_NOW_TERRATEST_ALLOW_APPLY"), "apply/destroy mode requires an explicit staging-only confirmation")
	}
}

func rootOptions(t *testing.T) *terraform.Options {
	t.Helper()
	varFile := os.Getenv("SYNTH_NOW_TERRATEST_VAR_FILE")
	require.NotEmpty(t, varFile, "set SYNTH_NOW_TERRATEST_VAR_FILE to a secure staging tfvars path")
	require.True(t, filepath.IsAbs(varFile), "use an absolute secure tfvars path")

	return &terraform.Options{
		TerraformDir:       terraformDirectory,
		VarFiles:           []string{varFile},
		NoColor:            true,
		Lock:               true,
		MaxRetries:         2,
		TimeBetweenRetries: 15 * time.Second,
	}
}

// TestStagingPlan verifies provider/module compatibility only. It never calls apply or destroy.
func TestStagingPlan(t *testing.T) {
	if os.Getenv("SYNTH_NOW_TERRATEST_PLAN") != "true" {
		t.Skip("set SYNTH_NOW_TERRATEST_PLAN=true to run the staging Terraform plan test")
	}
	requireStaging(t, "plan")

	options := rootOptions(t)
	planOutput, err := terraform.InitAndPlanE(t, options)
	require.NoError(t, err)
	require.Contains(t, planOutput, "Plan:")
	require.NotContains(t, planOutput, "destroy")
}

// TestExistingStagingOutputs validates a separately provisioned, approved staging stack. It never
// creates, changes, or destroys infrastructure. Configure backend variables in the CI environment.
func TestExistingStagingOutputs(t *testing.T) {
	if os.Getenv("SYNTH_NOW_TERRATEST_VERIFY_EXISTING") != "true" {
		t.Skip("set SYNTH_NOW_TERRATEST_VERIFY_EXISTING=true to inspect approved staging outputs")
	}
	requireStaging(t, "verify")

	options := rootOptions(t)
	options.BackendConfig = map[string]interface{}{
		"bucket":         os.Getenv("SYNTH_NOW_TERRATEST_STATE_BUCKET"),
		"key":            os.Getenv("SYNTH_NOW_TERRATEST_STATE_KEY"),
		"region":         os.Getenv("SYNTH_NOW_TERRATEST_STATE_REGION"),
		"dynamodb_table": os.Getenv("SYNTH_NOW_TERRATEST_STATE_LOCK_TABLE"),
		"encrypt":        true,
	}
	for key, value := range options.BackendConfig {
		require.NotEmpty(t, value, "set remote-state backend config for existing-stack verification: %s", key)
	}

	terraform.Init(t, options)
	accountID := terraform.Output(t, options, "aws_account_id")
	require.Equal(t, os.Getenv("SYNTH_NOW_TERRATEST_APPROVED_ACCOUNT_ID"), accountID)

	primaryCluster := terraform.Output(t, options, "primary_eks_cluster_name")
	secondaryCluster := terraform.Output(t, options, "secondary_eks_cluster_name")
	globalAurora := terraform.Output(t, options, "aurora_global_cluster_id")
	require.Contains(t, primaryCluster, "staging")
	require.Contains(t, secondaryCluster, "staging")
	require.Contains(t, globalAurora, "staging")
	require.NotEqual(t, primaryCluster, secondaryCluster)
}

// TestPrivateBucketCanary creates only an isolated uniquely named bucket fixture in the approved
// staging account, verifies versioning and public-access blocks via AWS APIs, and defers destroy.
func TestPrivateBucketCanary(t *testing.T) {
	if os.Getenv("SYNTH_NOW_TERRATEST_CANARY") != "true" {
		t.Skip("set SYNTH_NOW_TERRATEST_CANARY=true and explicit staging confirmation to run the canary")
	}
	requireStaging(t, "apply")

	region := os.Getenv("SYNTH_NOW_TERRATEST_PRIMARY_REGION")
	require.NotEmpty(t, region)
	uniqueID := strings.ToLower(random.UniqueId())
	bucketName := fmt.Sprintf("synth-now-staging-terratest-%s", uniqueID)

	fixtureDir := filepath.Join(terraformDirectory, "test", "fixtures", "private_bucket")
	options := &terraform.Options{
		TerraformDir: fixtureDir,
		Vars: map[string]interface{}{
			"name":        "synth-now-staging-terratest",
			"bucket_name": bucketName,
		},
		EnvVars: map[string]string{
			"AWS_REGION": region,
		},
		NoColor: true,
		Lock:    true,
	}
	defer terraform.Destroy(t, options)
	terraform.InitAndApply(t, options)

	sess, err := session.NewSession(&awsSDK.Config{Region: awsSDK.String(region)})
	require.NoError(t, err)
	client := s3.New(sess)

	versioning, err := client.GetBucketVersioning(&s3.GetBucketVersioningInput{Bucket: awsSDK.String(bucketName)})
	require.NoError(t, err)
	require.Equal(t, s3.BucketVersioningStatusEnabled, awsSDK.StringValue(versioning.Status))

	publicAccess, err := client.GetPublicAccessBlock(&s3.GetPublicAccessBlockInput{Bucket: awsSDK.String(bucketName)})
	require.NoError(t, err)
	require.True(t, awsSDK.BoolValue(publicAccess.PublicAccessBlockConfiguration.BlockPublicAcls))
	require.True(t, awsSDK.BoolValue(publicAccess.PublicAccessBlockConfiguration.BlockPublicPolicy))
	require.True(t, awsSDK.BoolValue(publicAccess.PublicAccessBlockConfiguration.IgnorePublicAcls))
	require.True(t, awsSDK.BoolValue(publicAccess.PublicAccessBlockConfiguration.RestrictPublicBuckets))
}
