provider "aws" {
  region  = "eu-west-2"
}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "7.0.1"

  cluster_name    = "terraform-cco"
  cluster_version = "1.14"

  subnets = ["subnet-189dd871", "subnet-4e46c734", "subnet-ea9e49a6"]
  vpc_id = "vpc-30aedd58"
  
  worker_groups = [
    {
      instance_type = "m4.large"
      asg_max_size  = 5
    }
  ]
}

data "aws_eks_cluster" "cluster" {
  name = module.eks.cluster_id  
}

data "aws_eks_cluster_auth" "cluster" {
  name = module.eks.cluster_id
}

provider "kubernetes" {
  host                   = data.aws_eks_cluster.cluster.endpoint
  cluster_ca_certificate = base64decode(data.aws_eks_cluster.cluster.certificate_authority.0.data)
  token                  = data.aws_eks_cluster_auth.cluster.token
  load_config_file       = false
  version                = "~> 1.9"
}

